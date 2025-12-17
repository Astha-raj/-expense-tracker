from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum
from django.utils.timezone import now
from django.http import HttpResponse
from django.core.paginator import Paginator

from datetime import timedelta, date
import csv
import json

from .models import Expense, MonthlyBudget, Category
from .forms import ExpenseForm


# ---------------- AUTH ----------------

def signup_view(request):
    form = UserCreationForm(request.POST or None)
    if form.is_valid():
        user = form.save()
        login(request, user)
        return redirect('dashboard')
    return render(request, 'expenses/signup.html', {'form': form})


def login_view(request):
    form = AuthenticationForm(data=request.POST or None)
    if form.is_valid():
        login(request, form.get_user())
        return redirect('dashboard')
    return render(request, 'expenses/login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('login')


# ---------------- DASHBOARD ----------------

@login_required
def dashboard_view(request):
    user = request.user
    today = date.today()

    # Monthly budget
    budget_obj = MonthlyBudget.objects.filter(
        user=user, month=today.month, year=today.year
    ).first()
    budget = budget_obj.amount if budget_obj else 0

    # Expenses (this month)
    expenses = Expense.objects.filter(
        user=user,
        date__month=today.month,
        date__year=today.year
    )

    total_expense = expenses.aggregate(
        total=Sum('amount')
    )['total'] or 0

    remaining = budget - total_expense
    overspent = remaining < 0

    # ---------- CATEGORY DATA ----------
    category_qs = (
        expenses
        .values('category__name')
        .annotate(total=Sum('amount'))
    )

    category_labels = [c['category__name'] for c in category_qs]
    category_values = [float(c['total']) for c in category_qs]

    # ---------- LAST 7 DAYS ----------
    # Build a complete 7-day series (including days with zero spend)
    last_7_days = today - timedelta(days=6)

    weekly_qs = (
        Expense.objects
        .filter(user=user, date__gte=last_7_days, date__lte=today)
        .values('date')
        .annotate(total=Sum('amount'))
        .order_by('date')
    )

    # map actual expense totals by date for quick lookup
    totals_map = {w['date']: float(w['total']) for w in weekly_qs}

    # produce labels/values for every day in the 7-day window
    weekly_labels = []
    weekly_values = []
    cursor = last_7_days
    while cursor <= today:
        weekly_labels.append(cursor.strftime("%d %b"))
        weekly_values.append(totals_map.get(cursor, 0.0))
        cursor = cursor + timedelta(days=1)

    return render(request, 'expenses/dashboard.html', {
        'total_expense': total_expense,
        'budget': budget,
        'remaining': remaining,
        'overspent': overspent,

        # IMPORTANT
        'category_labels': json.dumps(category_labels),
        'category_values': json.dumps(category_values),
        'weekly_labels': json.dumps(weekly_labels),
        'weekly_values': json.dumps(weekly_values),
    })

# ---------------- BUDGET ----------------

@login_required
def budget_settings(request):
    today = date.today()

    budget, _ = MonthlyBudget.objects.get_or_create(
        user=request.user,
        month=today.month,
        year=today.year,
        defaults={'amount': 0}
    )

    if request.method == 'POST':
        try:
            budget.amount = float(request.POST.get('amount'))
            budget.save()
            messages.success(request, "Budget updated successfully")
            return redirect('dashboard')
        except ValueError:
            messages.error(request, "Enter a valid amount")

    return render(request, 'expenses/budget_settings.html', {'budget': budget})


# ---------------- ADD EXPENSE ----------------

@login_required
def add_expense_view(request):
    categories = Category.objects.all()

    if request.method == "POST":
        form = ExpenseForm(request.POST)
        new_category = request.POST.get('new_category', '').strip()

        if form.is_valid():
            expense = form.save(commit=False)
            expense.user = request.user

            # Add new category if provided
            if new_category:
                category_obj, _ = Category.objects.get_or_create(name=new_category)
                expense.category = category_obj

            expense.save()
            messages.success(request, "Expense added successfully")
            return redirect('dashboard')
    else:
        form = ExpenseForm()

    return render(request, 'expenses/add_expense.html', {
        'form': form,
        'categories': categories
    })


# ---------------- VIEW EXPENSES ----------------

@login_required
def view_expenses_view(request):
    expenses = Expense.objects.filter(user=request.user)

    date_filter = request.GET.get('date_filter', 'all')
    category_filter = request.GET.get('category', 'all')
    search_query = request.GET.get('search', '')
    sort_option = request.GET.get('sort', 'date_desc')

    today = now().date()

    if date_filter == 'today':
        expenses = expenses.filter(date=today)
    elif date_filter == 'week':
        expenses = expenses.filter(date__gte=today - timedelta(days=7))
    elif date_filter == 'month':
        expenses = expenses.filter(date__gte=today.replace(day=1))

    if category_filter != 'all':
        expenses = expenses.filter(category__id=category_filter)

    if search_query:
        expenses = expenses.filter(note__icontains=search_query)

    if sort_option == 'date_asc':
        expenses = expenses.order_by('date')
    elif sort_option == 'amount_asc':
        expenses = expenses.order_by('amount')
    elif sort_option == 'amount_desc':
        expenses = expenses.order_by('-amount')
    else:
        expenses = expenses.order_by('-date')

    total_amount = expenses.aggregate(total=Sum('amount'))['total'] or 0

    paginator = Paginator(expenses, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    categories = Category.objects.all()

    return render(request, 'expenses/view_expenses.html', {
        'page_obj': page_obj,
        'total_amount': total_amount,
        'categories': categories,
        'date_filter': date_filter,
        'category_filter': category_filter,
        'search_query': search_query,
        'sort_option': sort_option,
    })


# ---------------- EXPORT CSV ----------------

@login_required
def export_expenses_csv(request):
    expenses = Expense.objects.filter(user=request.user).order_by('-date')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="expenses.csv"'

    writer = csv.writer(response)
    writer.writerow(['Date', 'Category', 'Amount', 'Note'])

    for exp in expenses:
        writer.writerow([exp.date, exp.category.name, exp.amount, exp.note])

    return response


# ---------------- EDIT / DELETE ----------------

@login_required
def edit_expense_view(request, pk):
    expense = get_object_or_404(Expense, pk=pk, user=request.user)

    if request.method == "POST":
        form = ExpenseForm(request.POST, instance=expense)
        if form.is_valid():
            form.save()
            messages.success(request, "Expense updated")
            return redirect('view_expenses')
    else:
        form = ExpenseForm(instance=expense)

    return render(request, 'expenses/edit_expense.html', {'form': form})


@login_required
def delete_expense_view(request, pk):
    expense = get_object_or_404(Expense, pk=pk, user=request.user)

    if request.method == "POST":
        expense.delete()
        messages.success(request, "Expense deleted")
        return redirect('view_expenses')

    return render(request, 'expenses/confirm_delete.html', {'expense': expense})
