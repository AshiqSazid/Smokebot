from django.shortcuts import render, redirect, get_object_or_404, reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from .forms import ProductReviewForm
from products.models import AllProducts
from django.contrib import messages
from .models import ProductReviews
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
import requests
import os

# ✅ Voicebot constants
GROQ_API_KEY = "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"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama3-70b-8192"

# ----------------------------
# 🔥 Voicebot API view
# ----------------------------
@csrf_exempt
def voicebot_api(request):
    if request.method == "POST":
        text = request.POST.get('text')
        if not text:
            return JsonResponse({'error': 'No text provided.'}, status=400)
        try:
            headers = {
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": text}
                ],
                "temperature": 0.7,
                "max_tokens": 1024
            }
            response = requests.post(GROQ_API_URL, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            reply = data.get("choices", [{}])[0].get("message", {}).get("content", "Sorry, no valid response.")
            return JsonResponse({'reply': reply})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Invalid request method.'}, status=405)

# ----------------------------
# 🔥 Product Reviews Views
# ----------------------------

class CreateReview(LoginRequiredMixin, View):
    """View to create a review from the product details page."""

    def get(self, request, product_id):
        product = get_object_or_404(AllProducts, id=product_id)
        form = ProductReviewForm()

        context = {
            'review_form': form,
            'product': product,
        }
        return render(request, 'reviews/review-form-page.html', context)

    def post(self, request, product_id):
        product = get_object_or_404(AllProducts, id=product_id)
        redirect_url = request.POST.get('redirect_url')

        if redirect_url != f'/products/{product.slug}/':
            redirect_url = f'/products/{product.slug}/'

        form = ProductReviewForm(request.POST)

        if form.is_valid():
            review = form.save(commit=False)
            review.product = product
            review.author = request.user
            review.save()
            messages.success(request, 'Review successfully added!')
            return redirect(redirect_url)
        else:
            messages.error(request, 'Failed to add review. Please ensure the form is valid.')
            return redirect('add_review', product_id)


class EditReview(LoginRequiredMixin, View):
    """View to edit a review."""

    def get(self, request, product_id, review_id):
        user = request.user
        review = get_object_or_404(ProductReviews, id=review_id)
        product = get_object_or_404(AllProducts, id=product_id)

        if user == review.author or user.is_superuser:
            form = ProductReviewForm(instance=review)
            edit_review = True
            context = {
                'review_form': form,
                'review': review,
                'product': product,
                'edit_review': edit_review,
                'user': user,
            }
            return render(request, 'reviews/review-form-page.html', context)
        else:
            messages.error(request, 'You do not have permission to edit this review.')
            return redirect('product_detail', product.slug)

    def post(self, request, product_id, review_id):
        review = get_object_or_404(ProductReviews, id=review_id)
        updated_review = ProductReviewForm(request.POST, instance=review)
        redirect_url = request.POST.get('redirect_url')

        if redirect_url != f'/products/{review.product.slug}/':
            redirect_url = f'/products/{review.product.slug}/'

        if updated_review.is_valid():
            updated_review.save()
            messages.success(request, 'Review successfully updated!')
            return redirect(redirect_url)
        else:
            messages.error(request, 'Failed to update review. Please ensure the form is valid.')
            return redirect('edit_review', review_id)


class DeleteReview(LoginRequiredMixin, View):
    """View to delete a review."""

    def post(self, request, product_id, review_id):
        review = get_object_or_404(ProductReviews, id=review_id)

        if not request.user.is_superuser and request.user != review.author:
            messages.error(request, 'Sorry, you don\'t have permission to delete this review.')
            return redirect('home')
        else:
            redirect_url = request.POST.get('redirect_url')
            if redirect_url != f'/products/{review.product.slug}/':
                redirect_url = f'/products/{review.product.slug}/'

            review.delete()
            messages.success(request, 'Review successfully deleted!')
            return redirect(redirect_url)
