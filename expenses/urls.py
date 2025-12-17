from django.urls import path
from django.contrib import admin
from . import views

urlpatterns = [
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('add/', views.add_expense_view, name='add_expense'),
    path('expenses/', views.view_expenses_view, name='view_expenses'),
    path('expenses/<int:pk>/edit/', views.edit_expense_view, name='edit_expense'),      
    path('expenses/<int:pk>/delete/', views.delete_expense_view, name='delete_expense'),
    path('expenses/export/', views.export_expenses_csv, name='export_expenses'),
    path('budget/', views.budget_settings, name='budget_settings'), 
    path('', views.dashboard_view, name='dashboard'),  # home → dashboard


]
