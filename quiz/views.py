import os

from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpRequest
from django.db.models import Count
from django.views.decorators.csrf import csrf_exempt
from .models import Quiz, Question, Answer
from django.core.paginator import Paginator
from typing import Optional

from google.oauth2 import id_token
from google.auth.transport import requests

from . import models


def start_quiz_view(request) -> HttpResponse:
    topics = Quiz.objects.all().annotate(questions_count=Count("question"))
    return render(request, "start.html", context={"topics": topics})


def get_questions(request, is_start=False) -> HttpResponse:
    if is_start:
        request = _reset_quiz(request)
        question = _get_first_question(request)
    else:
        question = _get_subsequent_question(request)
        if question is None:
            return get_finish(request)

    answers = Answer.objects.filter(question=question)
    request.session["question_id"] = (
        question.id
    )  # Update session state with current question id.

    return render(
        request,
        "partials/question.html",
        context={"question": question, "answers": answers},
    )


def _get_first_question(request) -> Question:
    quiz_id = request.POST["quiz_id"]
    return Question.objects.filter(quiz_id=quiz_id).order_by("id").first()


def _get_subsequent_question(request) -> Optional[Question]:
    quiz_id = request.POST["quiz_id"]
    previous_question_id = request.session["question_id"]

    try:
        return (
            Question.objects.filter(quiz_id=quiz_id, id__gt=previous_question_id)
            .order_by("id")
            .first()
        )
    except Question.DoesNotExist:  # I.e., there are no more questions.
        return None


def get_answer(request) -> HttpResponse:
    submitted_answer_id = request.POST["answer_id"]
    submitted_answer = Answer.objects.get(id=submitted_answer_id)

    if submitted_answer.is_correct:
        correct_answer = submitted_answer
        request.session["score"] = request.session.get("score", 0) + 1
    else:
        correct_answer = Answer.objects.get(
            question_id=submitted_answer.question_id, is_correct=True
        )

    return render(
        request,
        "partials/answer.html",
        context={
            "submitted_answer": submitted_answer,
            "answer": correct_answer,
        },
    )


def get_finish(request) -> HttpResponse:
    quiz = Question.objects.get(id=request.session["question_id"]).quiz
    questions_count = Question.objects.filter(quiz=quiz).count()
    score = request.session["score"]
    percent = int(score / questions_count * 100)
    request = _reset_quiz(request)

    return render(
        request,
        "partials/finish.html",
        context={
            "questions_count": questions_count,
            "score": score,
            "percent_score": percent,
        },
    )


def _reset_quiz(request) -> HttpRequest:
    """
    We reset the quiz state to allow the user to start another quiz.
    """
    if "question_id" in request.session:
        del request.session["question_id"]
    if "score" in request.session:
        del request.session["score"]
    return request


def sign_in(request) -> HttpResponse:
    return render(request, "sign_in.html")

@csrf_exempt
def auth_receiver(request):
    """
    Google calls this URL after the user has signed in with their Google account.
    """
    token = request.POST['credential']

    try:
        user_data = id_token.verify_oauth2_token(
            token, requests.Request(), os.environ['GOOGLE_OAUTH_CLIENT_ID']
        )
    except ValueError:
        return HttpResponse(status=403)

    # In a real app, I'd also save any new user here to the database. See below for a real example I wrote for Photon Designer.
    # You could also authenticate the user here using the details from Google (https://docs.djangoproject.com/en/4.2/topics/auth/default/#how-to-log-a-user-in)
    request.session['user_data'] = user_data

    return redirect('sign_in')

def sign_out(request) -> HttpResponse:
    if "user_data" in request.session:
        del request.session["user_data"]
    return redirect("sign-in")