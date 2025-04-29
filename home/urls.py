# urls.py

from django.urls import path
from home.views import HomePage, voicebot_post, CreateReview, EditReview, DeleteReview

urlpatterns = [
    path('', HomePage.as_view(), name='home'),  # ✅ Home page
    path('reviews/voicebot/', voicebot_post, name='voicebot_post'),  # ✅ Mic button sends here
    path('create/', CreateReview.as_view(), name='add_review'),  # ✅ Create review
    path('edit-review/<int:pk>/', EditReview.as_view(), name='edit_review'),  # ✅ Edit review
    path('delete-review/<int:pk>/', DeleteReview.as_view(), name='delete_review'),  # ✅ Delete review
]
