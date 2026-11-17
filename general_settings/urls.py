"""
URL configuration for general_settings project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path,include

from payroll.views import ( index_view,home_view,dashboard_view,add_employee_view,edit_employee_view,delete_employee_view,
add_department_view,edit_department_view,delete_department_view,
add_position_view,edit_position_view,delete_position_view,
add_salary_scale_view,edit_salary_scale_view,delete_salary_scale_view,
add_payroll_view,edit_payroll_view,delete_payroll_view,
add_payslip_view,edit_payslip_view,delete_payslip_view,download_payslip_view,
sign_up_view,
employee_profile_view,leave_request_view,staff_leave_requests_view,
review_leave_request_view,employee_payslips_view,
manager_employees_view,employee_payroll_requests_view,
manager_payroll_requests_view,review_payroll_request_view,
manager_employee_data_requests_view,review_employee_data_request_view,
staff_payroll_requests_view,complete_payroll_request_view,
staff_employee_data_requests_view,
)


urlpatterns = [
    path('admin/', admin.site.urls),
    path('',index_view,name ='index_page'),
    path('sign_up/',sign_up_view,name ='sign_up_page'),
    path(
        'accounts/login/',
        auth_views.LoginView.as_view(redirect_authenticated_user=True),
        name='login',
    ),
    path('accounts/',include('django.contrib.auth.urls')),
    path('home/',home_view, name = 'home_page'),
    path('dashboard/',dashboard_view, name='dashboard_page'),
    path('add_employee/',add_employee_view, name = 'add_employee_page'),
    path('edit_employee/<int:employee_id>/',edit_employee_view, name = "edit_employee_page"),
    path('delete_employee/<int:employee_id>/',delete_employee_view,name= "delete_employee_page"),
    #path
    path('add_department/',add_department_view, name = 'add_department_page'),
    path('edit_department/<int:department_id>/',edit_department_view, name = "edit_department_page"),
    path('delete_department/<int:department_id>/',delete_department_view,name= "delete_department_page"),
    #path
    path('add_position/',add_position_view, name = 'add_position_page'),
    path('edit_position/<int:position_id>/',edit_position_view, name = "edit_position_page"),
    path('delete_position/<int:position_id>/',delete_position_view,name= "delete_position_page"),
    #path
    path('add_salary_scale/',add_salary_scale_view, name = 'add_salary_scale_page'),
    path('edit_salary_scale/<int:salary_scale_id>/',edit_salary_scale_view, name = "edit_salary_scale_page"),
    path('delete_salary_scale/<int:salary_scale_id>/',delete_salary_scale_view,name= "delete_salary_scale_page"),
    #path
    path('add_payroll/',add_payroll_view, name = 'add_payroll_page'),
    path('edit_payroll/<int:payroll_id>/',edit_payroll_view, name = "edit_payroll_page"),
    path('delete_payroll/<int:payroll_id>/',delete_payroll_view,name= "delete_payroll_page"),
    #path
    path('add_payslip/',add_payslip_view, name = 'add_payslip_page'),
    path('edit_payslip/<int:payslip_id>/',edit_payslip_view, name = "edit_payslip_page"),
    path('delete_payslip/<int:payslip_id>/',delete_payslip_view,name= "delete_payslip_page"),
    path('payslip/<int:payslip_id>/download/',download_payslip_view,name="download_payslip_page"),
    path('profile/',employee_profile_view,name='employee_profile_page'),
    path('my-payslips/',employee_payslips_view,name='employee_payslips_page'),
    path('leave-requests/',leave_request_view,name='leave_request_page'),
    path('staff/leave-requests/',staff_leave_requests_view,name='staff_leave_requests_page'),
    path('staff/leave-requests/<int:leave_request_id>/review/',review_leave_request_view,name='review_leave_request_page'),
    path('manager/leave-requests/',staff_leave_requests_view,name='manager_leave_requests_page'),
    path('manager/leave-requests/<int:leave_request_id>/review/',review_leave_request_view,name='manager_review_leave_request_page'),
    path('manager/employees/',manager_employees_view,name='manager_employees_page'),
    path('payroll-requests/',employee_payroll_requests_view,name='employee_payroll_requests_page'),
    path('manager/payroll-requests/',manager_payroll_requests_view,name='manager_payroll_requests_page'),
    path('manager/payroll-requests/<int:request_id>/review/',review_payroll_request_view,name='review_payroll_request_page'),
    path('staff/payroll-requests/',staff_payroll_requests_view,name='staff_payroll_requests_page'),
    path('staff/payroll-requests/<int:request_id>/complete/',complete_payroll_request_view,name='complete_payroll_request_page'),
    path('staff/employee-data-requests/',staff_employee_data_requests_view,name='staff_employee_data_requests_page'),
    path('manager/employee-data-requests/',manager_employee_data_requests_view,name='manager_employee_data_requests_page'),
    path('manager/employee-data-requests/<int:request_id>/review/',review_employee_data_request_view,name='review_employee_data_request_page'),
]
