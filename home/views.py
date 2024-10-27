from django.shortcuts import render
import pdfplumber
from langdetect import detect

from django.shortcuts import render, redirect
from .models import Article
from star.models import Like
from .forms import ArticleReviewForm
from .forms import ArticleUploadForm
from .forms import ArticleSearchForm, ArticleFindForm
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from collections import Counter
from django.core.paginator import Paginator
from django.db.models import Count

from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lsa import LsaSummarizer


def home(request):
    articles = Article.objects.annotate(like_count=Count('like')).order_by('-created')
    num = articles.count()
    form = ArticleFindForm()

    if request.GET.get('search'):
        articles = articles.filter(body__contains=request.GET['search'])
        text = 'Search results'
    else:
        text = 'Latest articles'

    # Pagination
    paginator = Paginator(articles, 3)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'home.html', {'articles': page_obj, 'form': form, 'text': text, 'num': num})


def detail(request, article_id):
    article = get_object_or_404(Article, id=article_id)

    if request.method == 'POST':
        form = ArticleSearchForm(request.POST)
        if form.is_valid():
            pdf_path = article.pdf.path
            current_word = form.cleaned_data['word']
            next_sentence = ''
            with pdfplumber.open(pdf_path) as pdf_reader:
                found_current_word = False
                for page_num in range(len(pdf_reader.pages)):
                    page = pdf_reader.pages[page_num]
                    text = page.extract_text()
                    language = detect(text)
                    if language == 'fa':
                        text = text[::-1]
                    if current_word in text:
                        found_current_word = True
                        sentences = text.split('\n')
                        for i, sentence in enumerate(sentences):
                            if current_word in sentence:
                                if i + 1 < len(sentences):
                                    next_sentence = sentences[i] + sentences[i + 1]
                                else:
                                    messages.success(request, "No sentence found after the title.", 'danger')
                                break
                        break
                if not found_current_word:
                    messages.success(request, f"Word '{current_word}' not found in the PDF", 'danger')

            return render(request, 'detail.html', {'article': article, 'next_sentences': next_sentence, 'form': form})
    else:
        form = ArticleSearchForm()

        return render(request, 'detail.html', {'article': article, 'form': form})


def remove(request, article_id):
    article = Article.objects.get(id=article_id)
    article.owner.remove(request.user)
    messages.success(request, 'an article remove from your profile successfully', 'success')

    return redirect('home')


def add(request, article_id):
    article = Article.objects.get(id=article_id)
    article.owner.add(request.user)
    messages.success(request, 'an article add to your profile successfully', 'success')

    return redirect('home')


@login_required()
def upload(request):
    if request.method == 'POST':
        form = ArticleUploadForm(request.POST, request.FILES)
        if form.is_valid():
            article = Article(title=form.cleaned_data['title'], pdf=request.FILES['pdf'])
            article.save()
            article.owner.add(request.user)

            return redirect('review', article_id=article.id)
    else:
        form = ArticleUploadForm()

        return render(request, 'upload.html', {'form':form})


def review(request, article_id):
    article = Article.objects.get(id=article_id)
    if request.method == 'POST':
        form = ArticleReviewForm(request.POST, instance=article)
        if form.is_valid():
            form.save()
            messages.success(request, 'your Article created successfully', 'success')

            return redirect('home')
    else:
        form = ArticleReviewForm(instance=article)

        with pdfplumber.open(article.pdf.path) as pdf:
            text = ''
            for page in pdf.pages:
                text += page.extract_text()
            language = detect(text)
            if language == 'en':
                normalized_text = text
            else:
                normalized_text = text[::-1]

            parser = PlaintextParser.from_string(normalized_text, Tokenizer("english"))
            summarizer = LsaSummarizer()
            summary = summarizer(parser.document, 5)
            body = ' '.join(str(sentence) for sentence in summary)

    form.initial['body'] = body
    form.initial['lang'] = language

    return render(request, 'review.html', {'form':form, 'lang': language})