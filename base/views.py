from django.shortcuts import redirect, render
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
import os
from django.db.models import Q
from .models import Room, Topic, Message, User
from .forms import RoomForm, UserForm, MyUserCreationFomr
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages


#Changes:
from .badwords import contains_bad_words, load_bad_words
from django.core.mail import send_mail
from django.utils.crypto import get_random_string
from django.template.loader import render_to_string
from django.conf import settings

# Create your views here.


# rooms = [
#     {'id':1, 'name': 'Python'},
#     {'id':2, 'name': 'Design with me'},
#     {'id':3, 'name': 'FrontEnd Devs'},
#     {'id':4, 'name': 'BackEnd Devs'},
# ]
def loginPage(request):
    page ='login'
    if request.user.is_authenticated:        
        return redirect('home')

    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        try:
            user = User.objects.get(email=email)
        except:
            messages.error(request, 'User doesnot exist')
        
        user = authenticate(request, email=email, password=password)

        if user is not None:
            login(request, user)
           
            return redirect('home')
        else:
            messages.error(request, 'Email or password does not exist. Please try again')
            return render(request, 'base/login_register.html')
        

    context={'page':page}
    return render(request, 'base/login_register.html', context)

def logoutUser(request):
    logout(request)
    return redirect(home)

def resgisterPage(request):
    form = MyUserCreationFomr()

    if request.method =='POST':
        form = MyUserCreationFomr(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.username = user.username.lower()
            user.save()
            
            #Change:
            otp = get_random_string(length=6, allowed_chars='1234567890')
            
            request.session['user_data'] = {
                'email':user.email,
                'username': user.username,
                'password': user.password
            }
            #Send otp:
            request.session['registration_otp'] = otp
            
            subject = 'OTP for registration'
            message = f'Your OTP is: {otp}'
            from_email = settings.EMAIL_HOST_USER
            to_email = user.email
            send_mail(subject, message, from_email, [to_email])
            
            return redirect('verify_otp')
            # messages.success(request, "Account has been created!")
            # login(request, user)
            # return redirect('home')
    
    return render(request, 'base/login_register.html', {'form':form})

def verifyOtpPage(request):
    if request.method == 'POST':
        entered_otp = request.POST.get('otp')
        stored_otp = request.session.get('registration_otp')
        
        if entered_otp == stored_otp:
            del request.session['registration_otp']
            
            user = MyUserCreationFomr(request.session.get('user_data'))
            if user.is_valid():
                user_instance = user.save(commit=True)
                login(request, user_instance)
                messages.success(request, "Account has been created")
                return redirect('login')
            else:
                messages.error(request, "Account Created")
        
        else:
            messages.error(request, 'Invalid OTP')
    
    return render(request, 'base/verify_otp.html')


def home(request):
    q = request.GET.get('q') if request.GET.get('q') != None else ''

    rooms = Room.objects.filter(
        Q(topic__name__icontains=q) |
        Q(name__icontains=q) |
        Q(description__icontains=q)
        )
    topics = Topic.objects.all()
    room_count = rooms.count()
    room_messages = Message.objects.filter(Q(room__topic__name__icontains=q))

    context = {'rooms': rooms, 'topics':topics,
               'room_count':room_count, 'room_messages':room_messages}
    return render(request, 'base/home.html', context)

def room(request, pk):
    room = Room.objects.get(id=pk)
    room_messages=room.message_set.all()
    participants = room.participants.all()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_file_path = os.path.join(script_dir, 'badwords.csv')

    bad_words = load_bad_words(csv_file_path)
    if request.method == 'POST':
        try:
            message_body = request.POST.get('body')            
            if contains_bad_words(message_body, bad_words):
                messages.error(request, "Your message contains offensive words. Please be polite")
                return redirect('room', pk=room.id)
        
            else:
                message = Message.objects.create(
                user=request.user,
                room = room,
                body = request.POST.get('body')
            )
            room.participants.add(request.user)
            return redirect('room', pk=room.id)
        except:
            messages.error(request, "Could not find badwords")
            return redirect('home')
            
        
    context = {'room': room, 'room_messages':room_messages, 'participants':participants}
    return render(request, 'base/room.html', context)

def userProfile(request, pk):
    user = User.objects.get(id=pk)
    rooms = user.room_set.all()
    room_messages = user.message_set.all()
    topics = Topic.objects.all()
    context = {'user':user, 'rooms':rooms, 'room_messages':room_messages, 'topics':topics}
    return render(request, 'base/profile.html', context)


@login_required(login_url='login')
def createRoom(request):
    form = RoomForm()
    topics = Topic.objects.all()
    if request.method == 'POST':
        topic_name = request.POST.get('topic')
        topic, created= Topic.objects.get_or_create(name=topic_name)
        Room.objects.create(
            host=request.user,
            topic=topic,
            name=request.POST.get('name'),
            description=request.POST.get('description'),
        ) 
       
        # form = RoomForm(request.POST)
        # if form.is_valid():
        #     room = form.save(commit=False)
        #     room.host = request.user
        #     room.save()
        return redirect('home')

    context={'form':form, 'topics':topics}
    return render(request, 'base/room_form.html', context)

@login_required(login_url='login')
def updateRoom(request, pk):
    room = Room.objects.get(id=pk)
    form = RoomForm(instance=room)
    topics = Topic.objects.all()
    if request.user != room.host :
        return HttpResponse('You are not allowed to Update this')

    if request.method == 'POST':
        topic_name = request.POST.get('topic')
        topic, created= Topic.objects.get_or_create(name=topic_name)
        room.name = request.POST.get('name')
        room.topic = request.POST.get('topic')
        room.description = request.POST.get('description')
        room.save()
        return redirect('home')
    context = {'form':form, 'topics':topics, 'room':room}
    return render(request, 'base/room_form.html', context)

@login_required(login_url='login')
def deleteRoom(request, pk):
    room = Room.objects.get(id=pk)
    if request.user != room.host :
        return HttpResponse('You are not allowed to delete this')
    if request.method == 'POST':
        room.delete()
        return redirect('home')
    return render(request, 'base/delete.html',{'obj':room})

@login_required(login_url='login')
def deleteMessage(request, pk):
    message = Message.objects.get(id=pk)
    if request.user != message.user:
        return HttpResponse('You are not allowed to delete this')
    if request.method == 'POST':
        message.delete()
        return redirect('home')
    return render(request, 'base/delete.html',{'obj':message})

@login_required(login_url='login')
def updateUser(request):
    user=request.user
    form = UserForm(instance=user)

    if request.method == 'POST':
        form = UserForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            return redirect('user-profile', pk=user.id)

    return render(request, 'base/update-user.html', {'form':form})