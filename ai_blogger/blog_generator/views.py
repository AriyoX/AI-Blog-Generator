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
from pytube import YouTube
import assemblyai as aai
import google.generativeai as genai

# Create your views here.
@login_required
def index(request):
    return render(request, 'index.html')

@csrf_exempt # since it isnt in the script
def generate_blog(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            yt_link = data['link']
            # return JsonResponse({'content': yt_link})
        except Exception as e:
            return JsonResponse({'error':'Invalid data sent'}, status=400)
        
        # get title
        title = yt_title(yt_link)

        # get transcript
        transcription = get_transcription(yt_link)
        if not transcription:
            return JsonResponse({'error':"Failed to get transcript"}, status=500)
        
        # use gemini to generate blog
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
    
def yt_title(link):
    yt = YouTube(link)
    title = yt.title
    return title

def download_audio(link):
    yt = YouTube(link)
    video = yt.streams.filter(only_audio=True).first()
    out_file = video.download(output_path=settings.MEDIA_ROOT)
    base, ext = os.path.splitext(out_file)
    new_file = base + '.mp3'
    os.rename(out_file, new_file)
    return new_file

def get_transcription(link):
    audio_file = download_audio(link)
    aai.settings.api_key = "b94ab9bf90a04767bd7001daf125b57f"
    transcriber = aai.Transcriber()
    transcript = transcriber.transcribe(audio_file)
    # delete audio file after successful transcription
    if transcript.text:
        os.remove(audio_file)
    return transcript.text

def generate_blog_from_transcription(transcription):
    GOOGLE_API_KEY= "AIzaSyCBek4ojoK-IcYVPlAPxEXNRNtdEO4zVVU"
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-pro')
    transcript = transcription
    prompt = f"Based on the following transcript from a youtube video, write a comprehensive blog article. write it based on the transcript, but do not make it look like a youtube video, make it look like a proper blog article. Do not add any text styles to the content you produce:\n\n{transcript}\n\nArticle:"
    try:
      response = model.generate_content(prompt)
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