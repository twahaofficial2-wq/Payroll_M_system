from django.contrib import admin

# Register your models here.
from .models import (
    Department,
    Employee,
    EmployeeDataRequest,
    LeaveRequest,
    Payroll,
    PayrollCorrectionRequest,
    Payslip,
    Position,
    Salary_Scale,
)

#admin.site.register()
@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display =['department_name', 'manager']
    search_fields = ['department_name']
@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ['title','level','department_name']
@admin.register(Salary_Scale)
class Salary_ScaleAdmin(admin.ModelAdmin):
    list_display =['position','entry_level_salary','junior_level_salary','senior_level_salary']
@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ['First_name','last_name','user','gender','position','department_name','contact']
    list_filter = ['gender','department_name','position']
    search_fields = ['First_name','last_name','email','user__username']
@admin.register(Payroll)
class PayrollAdmin(admin.ModelAdmin):
    list_display = ['year','month','status']
@admin.register(Payslip)
class PayslipAdmin(admin.ModelAdmin):
    list_display = ['employee','payroll','gross_pay','net_pay']

@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ["employee", "leave_type", "start_date", "end_date", "status"]
    list_filter = ["status", "leave_type"]
    search_fields = ["employee__First_name", "employee__last_name", "reason"]

@admin.register(EmployeeDataRequest)
class EmployeeDataRequestAdmin(admin.ModelAdmin):
    list_display = ["department", "request_type", "employee", "status", "submitted_at"]
    list_filter = ["department", "request_type", "status"]
    search_fields = ["employee__First_name", "employee__last_name"]

@admin.register(PayrollCorrectionRequest)
class PayrollCorrectionRequestAdmin(admin.ModelAdmin):
    list_display = ["employee", "pay_period", "status", "submitted_at"]
    list_filter = ["status"]
    search_fields = ["employee__First_name", "employee__last_name", "pay_period"]
