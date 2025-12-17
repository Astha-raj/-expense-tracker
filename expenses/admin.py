from django.contrib import admin
from .models import Expense, MonthlyBudget, Category

admin.site.register(Expense)
admin.site.register(Category)
admin.site.register(MonthlyBudget)


