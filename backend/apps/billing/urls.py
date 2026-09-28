from django.urls import path

from apps.billing import views

urlpatterns = [
    path("billing/plans/", views.PlanListView.as_view(), name="plan-list"),
    path("billing/subscription/", views.SubscriptionDetailView.as_view(), name="subscription-detail"),
    path("billing/subscription/change-plan/", views.ChangePlanView.as_view(), name="subscription-change-plan"),
]
