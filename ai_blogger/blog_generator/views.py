import time
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.conf import settings
from .models import BlogPost
import json
import os
import re
from urllib.error import HTTPError, URLError
from pytube import YouTube
import assemblyai as aai
from dotenv import load_dotenv
load_dotenv()
from mistralai import Mistral
import requests
import yt_dlp

# Create your views here.
@login_required
def index(request):
    return render(request, 'index.html')

@csrf_exempt
def generate_blog(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            raw_link = data['link'].strip()
            
            # Normalize YouTube URL
            if 'youtu.be/' in raw_link:
                video_id = raw_link.split('/')[-1]
                yt_link = f'https://youtube.com/watch?v={video_id}'
            else:
                yt_link = raw_link.split('&')[0]  # Remove extra parameters

            # Validate URL format more flexibly
            if not re.search(r'youtube\.com/watch\?v=|youtu\.be/', yt_link):
                return JsonResponse({
                    'error': 'Invalid YouTube URL. Please provide a full YouTube video link.'
                }, status=400)

        except Exception as e:
            return JsonResponse({'error': 'Invalid data sent'}, status=400)
        
        # Get title with comprehensive error handling
        title = yt_title(yt_link)
        if not title:
            return JsonResponse({
                'error': 'Failed to fetch video title. Possible reasons:\n'
                         '- Invalid or private video\n'
                         '- Video might be age-restricted\n'
                         '- Temporary YouTube API issues\n'
                         '- Network connectivity problems'
            }, status=400)

        # get transcript
        transcription = get_transcription(yt_link)
        if not transcription:
            return JsonResponse({'error':"Failed to get transcript"}, status=500)
        
        # use mistral to generate blog
        blog_content = generate_blog_from_transcription(transcription)
        if not blog_content:
            return JsonResponse({'error':"Failed to generate blog article"}, status=500)
        
        # save blog article to database
        new_blog_article = BlogPost.objects.create(
            user = request.user,
            youtube_title = title,
            youtube_link = yt_link,
            generated_content = blog_content,
        )
        new_blog_article.save()

        # return blog article as response
        return JsonResponse({'content':blog_content})
    else:
        return JsonResponse({'error':'Invalid request method'}, status=405)

def normalize_youtube_url(raw_link):
    """
    Normalize various YouTube URL formats to a standard watch URL
    """
    # Handle different YouTube link formats
    patterns = [
        r'youtu\.be/([^&\s]+)',           # Shortened links
        r'youtube\.com/watch\?v=([^&\s]+)', # Standard watch URL
        r'youtube\.com/embed/([^&\s]+)',    # Embed URL
        r'youtube\.com/v/([^&\s]+)',        # V URL
    ]
    
    for pattern in patterns:
        match = re.search(pattern, raw_link)
        if match:
            video_id = match.group(1)
            return f'https://www.youtube.com/watch?v={video_id}'
    
    return None
  

def yt_title(link):
    try:
        # Try pytube first
        try:
            yt = YouTube(link)
            return yt.title
        except Exception:
            pass
        
        # Fallback to YouTube embeds API
        video_id = link.split('v=')[-1].split('&')[0]
        api_url = f'https://www.youtube.com/oembed?url=http://www.youtube.com/watch?v={video_id}&format=json'
        
        response = requests.get(api_url)
        if response.status_code == 200:
            return response.json().get('title')
        
        # Final fallback - direct requests
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(link, headers=headers)
        
        # Extract title using regex
        import re
        title_match = re.search(r'<title>(.*?) - YouTube</title>', response.text)
        if title_match:
            return title_match.group(1)
        
        return None
    
    except Exception as e:
        print(f"Title fetch error: {e}")
        return None
    
def download_audio(link):
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': os.path.join(settings.MEDIA_ROOT, '%(id)s.%(ext)s'),
        'quiet': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=True)
            audio_path = os.path.join(
                settings.MEDIA_ROOT, 
                f"{info['id']}.mp3"
            )
            return audio_path
    except Exception as e:
        print(f"Error downloading audio: {e}")
        return None

def get_transcription(link):
    audio_file = download_audio(link)
    aai.settings.api_key = os.environ.get('ASSEMBLYAI_API_KEY')
    transcriber = aai.Transcriber()
    transcript = transcriber.transcribe(audio_file)
    # delete audio file after successful transcription
    if transcript.text:
        os.remove(audio_file)
    return transcript.text

def generate_blog_from_transcription(transcription):
    api_key = os.environ.get("MISTRAL_API_KEY")
    client = Mistral(api_key=api_key)
    model = "mistral-small-latest"
    transcript = transcription
    prompt = f"Based on the following transcript from a youtube video, write a comprehensive blog article. write it based on the transcript, but do not make it look like a youtube video, make it look like a proper blog article. Do not add any text styles to the content you produce:\n\n{transcript}\n\nArticle:"
    try:
      response = client.chat.complete(
        model=model,
        messages=[
            {
                "role": "user",
                "content": prompt,
            },
        ]
      )
      response = response.choices[0].message.content
      generated_content = response.text.replace("*", "")
      return generated_content
    except Exception as e:
        return JsonResponse({'error':"Failed to generate blog article"}, status=500)

def blog_list(request):
    blog_articles = BlogPost.objects.filter(user=request.user)
    return render(request, "all-blogs.html", { 'blog_articles' : blog_articles })

def blog_details(request, pk):
    blog_article_detail = BlogPost.objects.get(id=pk)
    if request.user == blog_article_detail.user:
        return render(request, 'blog-details.html', { 'blog_article_detail' : blog_article_detail })

def user_login(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('/')
        else:
            error_message = "Invalid username or password"
            return render(request, 'login.html', {
                'error_message': error_message,
            })
    return render(request, 'login.html')

def user_signup(request):
    if request.method == 'POST':
        username = request.POST['username']
        email = request.POST['email']
        password = request.POST['password']
        repeat_password = request.POST['repeatPassword']

        if password == repeat_password:
            try:
                user = User.objects.create_user(username, email, password)
                login(request, user)
                return redirect('/')
            except Exception as e:
                error_message = 'Error creating account: ' + str(e)
                return render(request, 'signup.html', {'error_message': error_message})
        else:
            error_message = 'Passwords do not match'
            return render(request, 'signup.html', {'error_message': error_message})
    else:
        return render(request, 'signup.html')

def user_logout(request):
    logout(request)
    return redirect('/')

@login_required
def delete(request, pk):
    blogpost = get_object_or_404(BlogPost, pk=pk, user=request.user)
    blogpost.delete()

    return redirect('blog_generator:blog-list')