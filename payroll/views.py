from datetime import date
from decimal import Decimal
from io import BytesIO

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.db.models import Sum
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render, redirect
from django.core.paginator import Paginator
from django.utils import timezone
from django.views.decorators.http import require_POST
from payroll.forms import (
    DepartmentForm,
    EmployeeForm,
    EmployeeProfileForm,
    LeaveRequestForm,
    PayrollCorrectionRequestForm,
    PayrollForm,
    PayslipForm,
    PositionForm,
    Salary_ScaleForm,
)
from payroll.models import (
    Department,
    EmployeeDataRequest,
    Employee,
    LeaveRequest,
    Payroll,
    PayrollCorrectionRequest,
    Payslip,
    Position,
    Salary_Scale,
)
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

def index_view(request):
    return render(
        request,
        "index.html",
        {
            "employee_count": Employee.objects.count(),
            "payroll_count": Payroll.objects.count(),
            "payslip_count": Payslip.objects.count(),
        },
    )

@login_required
def home_view(request):
    if not request.user.is_staff:
        employee = Employee.objects.filter(user=request.user).first()
        payslips = (
            Payslip.objects.filter(employee=employee)
            .select_related("payroll")
            .order_by("-payroll__year", "-payroll__month")
            if employee
            else Payslip.objects.none()
        )
        leave_requests = (
            employee.leave_requests.all() if employee else LeaveRequest.objects.none()
        )
        latest_payslip = payslips.first()
        return render(
            request,
            "employee_portal.html",
            {
                "employee": employee,
                "payslip_count": payslips.count(),
                "latest_payslip": latest_payslip,
                "leave_request_count": leave_requests.count(),
                "pending_leave_count": leave_requests.filter(status="pending").count(),
                "recent_leave_requests": leave_requests[:3],
                "managed_department": Department.objects.filter(
                    manager=request.user
                ).first(),
                "pending_manager_leave_count": LeaveRequest.objects.filter(
                    employee__department_name__manager=request.user,
                    status="pending",
                ).exclude(employee__user=request.user).count(),
                "pending_manager_payroll_count": PayrollCorrectionRequest.objects.filter(
                    employee__department_name__manager=request.user,
                    status="pending",
                ).exclude(employee__user=request.user).count(),
                "pending_manager_data_count": EmployeeDataRequest.objects.filter(
                    department__manager=request.user,
                    status="pending",
                ).exclude(requested_by=request.user).count(),
            },
        )
    return render(request,'home.html')


def _linked_employee_or_home(request):
    employee = Employee.objects.filter(user=request.user).first()
    if employee is None:
        messages.warning(
            request,
            "Your account is not linked to an employee record yet. Ask payroll staff to link it from Employees > Edit.",
        )
        return None
    return employee


def _managed_department(user):
    if user.is_staff:
        return None
    employee = Employee.objects.filter(user=user).only("department_name_id").first()
    if employee is None:
        return None
    return Department.objects.filter(
        pk=employee.department_name_id, manager=user
    ).first()


def _manager_forbidden_response():
    return HttpResponseForbidden(
        "You do not have department manager access to this page."
    )


@login_required
def employee_payslips_view(request):
    employee = _linked_employee_or_home(request)
    if employee is None:
        return redirect("home_page")
    payslips = (
        Payslip.objects.filter(employee=employee)
        .select_related("payroll")
        .order_by("-payroll__year", "-payroll__month")
    )
    return render(
        request,
        "employee_payslips.html",
        {"employee": employee, "payslips": payslips},
    )


@staff_member_required(login_url="login")
def dashboard_view(request):
    latest_payroll = Payroll.objects.order_by("-year", "-month").first()
    current_payroll_totals = None
    if latest_payroll:
        totals = Payslip.objects.filter(payroll=latest_payroll).aggregate(
            gross_pay=Sum("gross_pay"),
            deductions=Sum("deductions"),
            net_pay=Sum("net_pay"),
        )
        current_payroll_totals = {
            key: value if value is not None else Decimal("0.00")
            for key, value in totals.items()
        }

    context = {
        'employee_count': Employee.objects.count(),
        'department_count': Department.objects.count(),
        'payroll_count': Payroll.objects.count(),
        'payslip_count': Payslip.objects.count(),
        'recent_payrolls': Payroll.objects.order_by('-year', '-month')[:5],
        'latest_payroll': latest_payroll,
        'current_payroll_totals': current_payroll_totals,
    }
    return render(request, 'dashboard.html', context)


def _employee_request_payload(cleaned_data):
    return {
        "First_name": cleaned_data["First_name"],
        "last_name": cleaned_data["last_name"],
        "contact": cleaned_data["contact"],
        "email": cleaned_data["email"],
        "department_name": cleaned_data["department_name"].pk,
        "position": cleaned_data["position"].pk,
        "hire_date": cleaned_data["hire_date"].isoformat(),
        "age": cleaned_data["age"],
        "gender": cleaned_data["gender"],
    }


@staff_member_required(login_url="login")
def add_employee_view(request):
    message =''
    if request.method == "POST":
        employee_form = EmployeeForm(request.POST)

        if employee_form.is_valid():
            user_model = get_user_model()
            with transaction.atomic():
                department = employee_form.cleaned_data["department_name"]
                manager_review_required = department.manager_id is not None
                user = user_model.objects.create_user(
                    username=employee_form.cleaned_data["username"],
                    password=employee_form.cleaned_data["password1"],
                    email=employee_form.cleaned_data["email"],
                    is_active=not manager_review_required,
                )
                if manager_review_required:
                    EmployeeDataRequest.objects.create(
                        department=department,
                        account=user,
                        requested_by=request.user,
                        request_type="new",
                        proposed_data=_employee_request_payload(
                            employee_form.cleaned_data
                        ),
                    )
                    message = (
                        "Employee details submitted for department manager approval. "
                        "The login stays inactive until approved."
                    )
                else:
                    employee = employee_form.save(commit=False)
                    employee.user = user
                    employee.save()
                    message = "Employee and login account added successfully."
    else:
        employee_form = EmployeeForm()

    search_query = request.GET.get("q", "").strip()
    selected_department = request.GET.get("department", "").strip()
    if not selected_department.isdigit():
        selected_department = ""
    employees = Employee.objects.select_related(
        "department_name", "position", "user"
    ).order_by("last_name", "First_name")
    if search_query:
        employees = employees.filter(
            Q(First_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
            | Q(email__icontains=search_query)
            | Q(contact__icontains=search_query)
        )
    if selected_department:
        employees = employees.filter(department_name_id=selected_department)
    employee_page = Paginator(employees, 10).get_page(request.GET.get("page"))

    context = {
        'form':employee_form,
        'msg':message,
        'employees':employee_page.object_list,
        'employee_page': employee_page,
        'departments': Department.objects.order_by("department_name"),
        'search_query': search_query,
        'selected_department': selected_department,
    }
    return render(request,"add_employee.html",context)

@staff_member_required(login_url="login")
def edit_employee_view(request,employee_id):
    employee = get_object_or_404(Employee, id=employee_id)

    if request.method == "POST":
        employee_form = EmployeeForm(
            request.POST, instance=employee, include_account=False
        )

        if employee_form.is_valid():
            proposed_department = employee_form.cleaned_data["department_name"]
            approval_department = (
                employee.department_name
                if employee.department_name.manager_id
                else proposed_department
            )
            if approval_department.manager_id:
                if EmployeeDataRequest.objects.filter(
                    employee=employee, status="pending"
                ).exists():
                    messages.error(
                        request,
                        "This employee already has a change awaiting manager review.",
                    )
                    return redirect("add_employee_page")
                proposed_data = _employee_request_payload(
                    employee_form.cleaned_data
                )
                proposed_data["user_id"] = employee_form.cleaned_data["user"].pk \
                    if employee_form.cleaned_data["user"] else None
                EmployeeDataRequest.objects.create(
                    department=approval_department,
                    employee=employee,
                    requested_by=request.user,
                    request_type="update",
                    proposed_data=proposed_data,
                )
                messages.success(
                    request, "Employee changes submitted for manager approval."
                )
                return redirect("add_employee_page")
            with transaction.atomic():
                employee = employee_form.save()
                employee.user = employee_form.cleaned_data["user"]
                employee.save(update_fields=["user"])
                if employee.user_id and employee.user.email != employee.email:
                    employee.user.email = employee.email
                    employee.user.save(update_fields=["email"])
            messages.success(request, "Employee details and login link saved.")
            return redirect('add_employee_page')
        else:
            message = "invalid input provided"
    else:
        #employee_form = EmployeeForm(request.POST, instance = employee)
        employee_form = EmployeeForm(instance=employee, include_account=False)

    context = {
        'form':employee_form,
        'employee': employee
    }
    return render(request,'edit_employee.html',context)


@login_required
def employee_profile_view(request):
    employee = _linked_employee_or_home(request)
    if employee is None:
        return redirect("home_page")
    employee = Employee.objects.select_related(
        "department_name", "position"
    ).get(pk=employee.pk)
    if request.method == "POST":
        form = EmployeeProfileForm(request.POST, instance=employee)
        if form.is_valid():
            if employee.department_name.manager_id:
                if EmployeeDataRequest.objects.filter(
                    employee=employee, status="pending"
                ).exists():
                    messages.error(
                        request,
                        "A profile change is already awaiting manager review.",
                    )
                    return redirect("employee_profile_page")
                EmployeeDataRequest.objects.create(
                    department=employee.department_name,
                    employee=employee,
                    requested_by=request.user,
                    request_type="profile",
                    proposed_data={
                        "email": form.cleaned_data["email"],
                        "contact": form.cleaned_data["contact"],
                    },
                )
                messages.success(
                    request,
                    "Your profile changes were submitted for manager approval.",
                )
            else:
                employee = form.save()
                request.user.email = employee.email
                request.user.save(update_fields=["email"])
                messages.success(request, "Your contact details have been updated.")
            return redirect("employee_profile_page")
    else:
        form = EmployeeProfileForm(instance=employee)
    return render(
        request,
        "employee_profile.html",
        {
            "employee": employee,
            "form": form,
            "pending_data_request": EmployeeDataRequest.objects.filter(
                employee=employee, status="pending"
            ).first(),
        },
    )


@login_required
def leave_request_view(request):
    employee = _linked_employee_or_home(request)
    if employee is None:
        return redirect("home_page")
    if request.method == "POST":
        form = LeaveRequestForm(request.POST)
        if form.is_valid():
            leave_request = form.save(commit=False)
            leave_request.employee = employee
            leave_request.save()
            messages.success(request, "Your leave request has been submitted.")
            return redirect("leave_request_page")
    else:
        form = LeaveRequestForm()
    return render(
        request,
        "leave_request.html",
        {
            "form": form,
            "leave_requests": employee.leave_requests.all(),
        },
    )


@login_required
def staff_leave_requests_view(request):
    department = _managed_department(request.user)
    if not request.user.is_staff and department is None:
        return _manager_forbidden_response()
    leave_requests = LeaveRequest.objects.select_related(
        "employee", "employee__department_name"
    )
    if department:
        leave_requests = leave_requests.filter(
            employee__department_name=department
        ).exclude(employee__user=request.user)
    return render(
        request,
        "staff_leave_requests.html",
        {"leave_requests": leave_requests, "manager_view": department is not None},
    )


@login_required
@require_POST
def review_leave_request_view(request, leave_request_id):
    leave_request = get_object_or_404(LeaveRequest, pk=leave_request_id)
    department = _managed_department(request.user)
    if not request.user.is_staff and department is None:
        return _manager_forbidden_response()
    if department and leave_request.employee.department_name_id != department.pk:
        return _manager_forbidden_response()
    if department and leave_request.employee.user_id == request.user.pk:
        return _manager_forbidden_response()
    decision = request.POST.get("decision")
    if decision not in {"approved", "rejected"}:
        messages.error(request, "Choose approve or reject for this leave request.")
        return redirect(
            "manager_leave_requests_page" if department else "staff_leave_requests_page"
        )
    if leave_request.status != "pending":
        messages.info(request, "This leave request has already been reviewed.")
        return redirect(
            "manager_leave_requests_page" if department else "staff_leave_requests_page"
        )
    leave_request.status = decision
    leave_request.save(update_fields=["status"])
    messages.success(
        request,
        f"Leave request {leave_request.get_status_display().lower()}.",
    )
    return redirect(
        "manager_leave_requests_page" if department else "staff_leave_requests_page"
    )


@login_required
def manager_employees_view(request):
    department = _managed_department(request.user)
    if department is None:
        return _manager_forbidden_response()
    employees = Employee.objects.filter(department_name=department).select_related(
        "position"
    ).order_by("last_name", "First_name")
    return render(
        request,
        "manager_employees.html",
        {"department": department, "employees": employees},
    )


@login_required
def employee_payroll_requests_view(request):
    employee = _linked_employee_or_home(request)
    if employee is None:
        return redirect("home_page")
    if request.method == "POST":
        form = PayrollCorrectionRequestForm(request.POST)
        if form.is_valid():
            payroll_request = form.save(commit=False)
            payroll_request.employee = employee
            payroll_request.save()
            messages.success(
                request,
                "Your payroll correction request has been sent to your department manager.",
            )
            return redirect("employee_payroll_requests_page")
    else:
        form = PayrollCorrectionRequestForm()
    return render(
        request,
        "payroll_requests.html",
        {
            "form": form,
            "payroll_requests": employee.payroll_requests.all(),
            "manager_view": False,
        },
    )


@login_required
def manager_payroll_requests_view(request):
    department = _managed_department(request.user)
    if department is None:
        return _manager_forbidden_response()
    payroll_requests = PayrollCorrectionRequest.objects.filter(
        employee__department_name=department
    ).exclude(employee__user=request.user).select_related("employee")
    return render(
        request,
        "payroll_requests.html",
        {
            "payroll_requests": payroll_requests,
            "manager_view": True,
            "department": department,
        },
    )


@login_required
@require_POST
def review_payroll_request_view(request, request_id):
    department = _managed_department(request.user)
    if department is None:
        return _manager_forbidden_response()
    payroll_request_query = PayrollCorrectionRequest.objects.select_related("employee")
    payroll_request_query = payroll_request_query.filter(
        employee__department_name=department
    )
    payroll_request = get_object_or_404(payroll_request_query, pk=request_id)
    if department and payroll_request.employee.user_id == request.user.pk:
        return _manager_forbidden_response()
    if payroll_request.status != "pending":
        messages.info(request, "This payroll request has already been reviewed.")
        return redirect("manager_payroll_requests_page")
    decision = request.POST.get("decision")
    if decision not in {"approved", "rejected"}:
        messages.error(request, "Choose approve or reject for this request.")
        return redirect("manager_payroll_requests_page")
    payroll_request.status = decision
    payroll_request.reviewed_by = request.user
    payroll_request.reviewed_at = timezone.now()
    payroll_request.review_note = request.POST.get("review_note", "").strip()
    payroll_request.save(
        update_fields=[
            "status",
            "reviewed_by",
            "reviewed_at",
            "review_note",
        ]
    )
    messages.success(
        request,
        "Request approved and referred to payroll staff."
        if decision == "approved"
        else "Request rejected.",
    )
    return redirect("manager_payroll_requests_page")


@staff_member_required(login_url="login")
def staff_payroll_requests_view(request):
    payroll_requests = PayrollCorrectionRequest.objects.select_related(
        "employee", "employee__department_name"
    ).filter(status__in=("approved", "completed"))
    return render(
        request,
        "payroll_requests.html",
        {"payroll_requests": payroll_requests, "staff_view": True},
    )


@staff_member_required(login_url="login")
@require_POST
def complete_payroll_request_view(request, request_id):
    payroll_request = get_object_or_404(
        PayrollCorrectionRequest, pk=request_id, status="approved"
    )
    payroll_request.status = "completed"
    payroll_request.processing_note = request.POST.get("review_note", "").strip()
    payroll_request.processed_by = request.user
    payroll_request.processed_at = timezone.now()
    payroll_request.save(
        update_fields=[
            "status",
            "processing_note",
            "processed_by",
            "processed_at",
        ]
    )
    messages.success(request, "Payroll request marked as completed.")
    return redirect("staff_payroll_requests_page")


@login_required
def manager_employee_data_requests_view(request):
    department = _managed_department(request.user)
    if department is None:
        return _manager_forbidden_response()
    data_requests = (
        EmployeeDataRequest.objects.filter(department=department)
        .exclude(requested_by=request.user)
        .select_related("employee", "account", "requested_by")
    )
    position_titles = dict(
        Position.objects.filter(
            pk__in=[
                item.proposed_data.get("position")
                for item in data_requests
                if item.proposed_data.get("position")
            ]
        ).values_list("pk", "title")
    )
    department_names = dict(
        Department.objects.filter(
            pk__in=[
                item.proposed_data.get("department_name")
                for item in data_requests
                if item.proposed_data.get("department_name")
            ]
        ).values_list("pk", "department_name")
    )
    for data_request in data_requests:
        position_id = data_request.proposed_data.get("position")
        data_request.proposed_position_title = position_titles.get(position_id)
        proposed_department_id = data_request.proposed_data.get("department_name")
        data_request.proposed_department_name = department_names.get(
            proposed_department_id
        )
    return render(
        request,
        "manager_employee_data_requests.html",
        {"department": department, "data_requests": data_requests},
    )


@staff_member_required(login_url="login")
def staff_employee_data_requests_view(request):
    data_requests = EmployeeDataRequest.objects.filter(status="pending").select_related(
        "department", "employee", "account", "requested_by"
    )
    position_titles = dict(
        Position.objects.filter(
            pk__in=[
                item.proposed_data.get("position")
                for item in data_requests
                if item.proposed_data.get("position")
            ]
        ).values_list("pk", "title")
    )
    department_names = dict(
        Department.objects.filter(
            pk__in=[
                item.proposed_data.get("department_name")
                for item in data_requests
                if item.proposed_data.get("department_name")
            ]
        ).values_list("pk", "department_name")
    )
    for data_request in data_requests:
        data_request.proposed_position_title = position_titles.get(
            data_request.proposed_data.get("position")
        )
        data_request.proposed_department_name = department_names.get(
            data_request.proposed_data.get("department_name")
        )
    return render(
        request,
        "manager_employee_data_requests.html",
        {"data_requests": data_requests, "staff_view": True},
    )


@login_required
@require_POST
def review_employee_data_request_view(request, request_id):
    department = _managed_department(request.user)
    if not request.user.is_staff and department is None:
        return _manager_forbidden_response()
    data_request_query = EmployeeDataRequest.objects.select_related(
        "employee", "account"
    )
    if department:
        data_request_query = data_request_query.filter(department=department)
    data_request = get_object_or_404(data_request_query, pk=request_id)
    if department and data_request.requested_by_id == request.user.pk:
        return _manager_forbidden_response()
    if data_request.status != "pending":
        messages.info(request, "This employee-data request has already been reviewed.")
        return redirect(
            "manager_employee_data_requests_page"
            if department
            else "staff_employee_data_requests_page"
        )
    decision = request.POST.get("decision")
    if decision not in {"approved", "rejected"}:
        messages.error(request, "Choose approve or reject for this request.")
        return redirect(
            "manager_employee_data_requests_page"
            if department
            else "staff_employee_data_requests_page"
        )
    if decision == "approved":
        with transaction.atomic():
            proposed_data = data_request.proposed_data.copy()
            if data_request.request_type == "new":
                proposed_data["department_name"] = get_object_or_404(
                    Department, pk=proposed_data["department_name"]
                )
                proposed_data["position"] = get_object_or_404(
                    Position, pk=proposed_data["position"]
                )
                proposed_data["hire_date"] = date.fromisoformat(
                    proposed_data["hire_date"]
                )
                if data_request.account is None:
                    return HttpResponseForbidden(
                        "The pending employee login no longer exists."
                    )
                employee = Employee(**proposed_data, user=data_request.account)
                try:
                    employee.full_clean()
                except ValidationError as error:
                    messages.error(
                        request,
                        "Could not approve this employee record: "
                        + "; ".join(error.messages),
                    )
                    return redirect(
                        "manager_employee_data_requests_page"
                        if department
                        else "staff_employee_data_requests_page"
                    )
                employee.save()
                if data_request.account_id:
                    account = data_request.account
                    account.is_active = True
                    account.save(update_fields=["is_active"])
                data_request.employee = employee
            else:
                employee = data_request.employee
                if employee is None:
                    return HttpResponseForbidden(
                        "The employee record for this request no longer exists."
                    )
                proposed_department_id = proposed_data.get("department_name")
                if (
                    department
                    and proposed_department_id
                    and proposed_department_id != department.pk
                ):
                    messages.error(
                        request,
                        "Department transfers must be reviewed by payroll staff.",
                    )
                    return redirect("manager_employee_data_requests_page")
                fields_to_update = [
                    "First_name",
                    "last_name",
                    "contact",
                    "email",
                    "department_name",
                    "position",
                    "hire_date",
                    "age",
                    "gender",
                ]
                for field in fields_to_update:
                    if field in proposed_data:
                        value = proposed_data[field]
                        if field == "department_name":
                            value = get_object_or_404(Department, pk=value)
                        elif field == "position":
                            value = get_object_or_404(Position, pk=value)
                        elif field == "hire_date":
                            value = date.fromisoformat(value)
                        setattr(employee, field, value)
                if "user_id" in proposed_data:
                    employee.user_id = proposed_data["user_id"]
                try:
                    employee.full_clean()
                except ValidationError as error:
                    messages.error(
                        request,
                        "Could not approve these employee changes: "
                        + "; ".join(error.messages),
                    )
                    return redirect(
                        "manager_employee_data_requests_page"
                        if department
                        else "staff_employee_data_requests_page"
                    )
                employee.save()
                if employee.user_id and "email" in proposed_data:
                    employee.user.email = employee.email
                    employee.user.save(update_fields=["email"])
            data_request.status = decision
            data_request.employee = employee
            data_request.reviewed_by = request.user
            data_request.reviewed_at = timezone.now()
            data_request.review_note = request.POST.get("review_note", "").strip()
            data_request.save(
                update_fields=[
                    "status",
                    "employee",
                    "reviewed_by",
                    "reviewed_at",
                    "review_note",
                ]
            )
    else:
        if data_request.request_type == "new" and data_request.account_id:
            data_request.account.delete()
            data_request.account = None
        data_request.status = decision
        data_request.reviewed_by = request.user
        data_request.reviewed_at = timezone.now()
        data_request.review_note = request.POST.get("review_note", "").strip()
        data_request.save(
            update_fields=[
                "status",
                "reviewed_by",
                "reviewed_at",
                "review_note",
            ]
        )
    messages.success(
        request,
        "Employee details approved."
        if decision == "approved"
        else "Employee-data request rejected.",
    )
    return redirect(
        "manager_employee_data_requests_page"
        if department
        else "staff_employee_data_requests_page"
    )

@staff_member_required(login_url="login")
@require_POST
def delete_employee_view(request,employee_id):
    employee = get_object_or_404(Employee, id=employee_id)

    employee.delete()
    return redirect('add_employee_page')

#dept#############################################################################################
@staff_member_required(login_url="login")
def add_department_view(request):
    message =''
    if request.method == "POST":
        department_form = DepartmentForm(request.POST)

        if department_form.is_valid():
            department_form.save()
            message='Department Added Successfully'
    else:
        department_form = DepartmentForm()

    departments = Department.objects.all()

    context = {
        'form':department_form,
        'msg':message,
        'departments':departments
    }
    return render(request,"add_department.html",context)

@staff_member_required(login_url="login")
def edit_department_view(request,department_id):
    department = get_object_or_404(Department, id=department_id)

    if request.method == "POST":
        department_form = DepartmentForm(request.POST,instance = department)

        if department_form.is_valid():
            department_form.save()
            message = "Changes Saved Succesfully"
            return redirect('add_department_page')
        else:
            message = "invalid input provided"
    else:
        #employee_form = EmployeeForm(request.POST, instance = employee)
        department_form = DepartmentForm(instance = department)

    context = {
        'form':department_form,
        'employee': department
    }
    return render(request,'edit_department.html',context)

@staff_member_required(login_url="login")
@require_POST
def delete_department_view(request,department_id):
    department = get_object_or_404(Department, id=department_id)

    try:
        department.delete()
    except ProtectedError:
        messages.error(
            request,
            "This department still has employees assigned to its positions. "
            "Reassign those employees before deleting the department.",
        )
    return redirect('add_department_page')

#POSITION##############################################################3

@staff_member_required(login_url="login")
def add_position_view(request):
    message =''
    if request.method == "POST":
        position_form = PositionForm(request.POST)

        if position_form.is_valid():
            position_form.save()
            message='position Added Successfully'
    else:
        position_form = PositionForm()

    positions = Position.objects.all()

    context = {
        'form':position_form,
        'msg':message,
        'positions':positions
    }
    return render(request,"add_position.html",context)

@staff_member_required(login_url="login")
def edit_position_view(request,position_id):
    position = get_object_or_404(Position, id=position_id)

    if request.method == "POST":
        position_form = PositionForm(request.POST,instance = position)

        if position_form.is_valid():
            position_form.save()
            message = "Changes Saved Succesfully"
            return redirect('add_position_page')
        else:
            message = "invalid input provided"
    else:
        #employee_form = EmployeeForm(request.POST, instance = employee)
        position_form = PositionForm(instance = position)

    context = {
        'form':position_form,
        'employee': position
    }
    return render(request,'edit_position.html',context)

@staff_member_required(login_url="login")
@require_POST
def delete_position_view(request,position_id):
    position = get_object_or_404(Position, id=position_id)

    try:
        position.delete()
    except ProtectedError:
        messages.error(
            request,
            "This position is assigned to employees. Reassign them before deleting it.",
        )
    return redirect('add_position_page')


#SALARY_SCALE#############################################################3

@staff_member_required(login_url="login")
def add_salary_scale_view(request):
    message =''
    if request.method == "POST":
        salary_scale_form = Salary_ScaleForm(request.POST)

        if salary_scale_form.is_valid():
            salary_scale_form.save()
            message='salary_scale Added Successfully'
    else:
        salary_scale_form = Salary_ScaleForm()

    salary_scales = Salary_Scale.objects.all()

    context = {
        'form':salary_scale_form,
        'msg':message,
        'salary_scales':salary_scales
    }
    return render(request,"add_salary_scale.html",context)

@staff_member_required(login_url="login")
def edit_salary_scale_view(request,salary_scale_id):
    salary_scale = get_object_or_404(Salary_Scale, id=salary_scale_id)

    if request.method == "POST":
        salary_scale_form = Salary_ScaleForm(request.POST,instance = salary_scale)

        if salary_scale_form.is_valid():
            salary_scale_form.save()
            message = "Changes Saved Succesfully"
            return redirect('add_salary_scale_page')
        else:
            message = "invalid input provided"
    else:
        #employee_form = EmployeeForm(request.POST, instance = employee)
        salary_scale_form = Salary_ScaleForm(instance = salary_scale)

    context = {
        'form':salary_scale_form,
        'salary_scale': salary_scale
    }
    return render(request,'edit_salary_scale.html',context)

@staff_member_required(login_url="login")
@require_POST
def delete_salary_scale_view(request,salary_scale_id):
    salary_scale = get_object_or_404(Salary_Scale, id=salary_scale_id)

    salary_scale.delete()
    return redirect('add_salary_scale_page')

#PAYROLL#############################################################3

@staff_member_required(login_url="login")
def add_payroll_view(request):
    message =''
    if request.method == "POST":
        payroll_form = PayrollForm(request.POST)

        if payroll_form.is_valid():
            payroll_form.save()
            message='payroll Added Successfully'
    else:
        payroll_form = PayrollForm()

    payrolls = Payroll.objects.all()

    context = {
        'form':payroll_form,
        'msg':message,
        'payrolls':payrolls
    }
    return render(request,"add_payroll.html",context)

@staff_member_required(login_url="login")
def edit_payroll_view(request,payroll_id):
    payroll = get_object_or_404(Payroll, id=payroll_id)

    if request.method == "POST":
        payroll_form = PayrollForm(request.POST,instance = payroll)

        if payroll_form.is_valid():
            payroll_form.save()
            message = "Changes Saved Succesfully"
            return redirect('add_payroll_page')
        else:
            message = "invalid input provided"
    else:
        #employee_form = EmployeeForm(request.POST, instance = employee)
        payroll_form = PayrollForm(instance = payroll)

    context = {
        'form':payroll_form,
        'payroll': payroll
    }
    return render(request,'edit_payroll.html',context)

@staff_member_required(login_url="login")
@require_POST
def delete_payroll_view(request,payroll_id):
    payroll = get_object_or_404(Payroll, id=payroll_id)

    payroll.delete()
    return redirect('add_payroll_page')



#PAYROLL#############################################################3

@staff_member_required(login_url="login")
def add_payslip_view(request):
    message =''
    if request.method == "POST":
        payslip_form = PayslipForm(request.POST)

        if payslip_form.is_valid():
            payslip_form.save()
            message='payslip Added Successfully'
    else:
        payslip_form = PayslipForm()

    search_query = request.GET.get("q", "").strip()
    selected_payroll = request.GET.get("payroll", "").strip()
    selected_status = request.GET.get("status", "").strip()
    if not selected_payroll.isdigit():
        selected_payroll = ""
    payslips = Payslip.objects.select_related(
        "employee", "payroll"
    ).order_by("-payroll__year", "-payroll__month", "employee__last_name")
    if search_query:
        payslips = payslips.filter(
            Q(employee__First_name__icontains=search_query)
            | Q(employee__last_name__icontains=search_query)
            | Q(employee__email__icontains=search_query)
            | Q(pay_period__icontains=search_query)
        )
    if selected_payroll:
        payslips = payslips.filter(payroll_id=selected_payroll)
    if selected_status:
        payslips = payslips.filter(payroll__status__iexact=selected_status)
    payslip_page = Paginator(payslips, 10).get_page(request.GET.get("page"))

    context = {
        'form':payslip_form,
        'msg':message,
        'payslips':payslip_page.object_list,
        'payslip_page': payslip_page,
        'payroll_periods': Payroll.objects.order_by("-year", "-month"),
        'payroll_statuses': Payroll.objects.order_by()
        .values_list("status", flat=True)
        .distinct(),
        'search_query': search_query,
        'selected_payroll': selected_payroll,
        'selected_status': selected_status,
    }
    return render(request,"add_payslip.html",context)

@staff_member_required(login_url="login")
def edit_payslip_view(request,payslip_id):
    payslip = get_object_or_404(Payslip, id=payslip_id)

    if request.method == "POST":
        payslip_form = PayslipForm(request.POST,instance = payslip)

        if payslip_form.is_valid():
            payslip_form.save()
            message = "Changes Saved Succesfully"
            return redirect('add_payslip_page')
        else:
            message = "invalid input provided"
    else:
        #employee_form = EmployeeForm(request.POST, instance = employee)
        payslip_form = PayslipForm(instance = payslip)

    context = {
        'form':payslip_form,
        'payroll': payslip
    }
    return render(request,'edit_payslip.html',context)

@staff_member_required(login_url="login")
@require_POST
def delete_payslip_view(request,payslip_id):
    payslip = get_object_or_404(Payslip, id=payslip_id)

    payslip.delete()
    return redirect('add_payslip_page')

@login_required
def download_payslip_view(request, payslip_id):
    payslip = get_object_or_404(
        Payslip.objects.select_related(
            "employee", "employee__department_name", "employee__position", "payroll"
        ),
        pk=payslip_id,
    )
    if not request.user.is_staff and payslip.employee.user_id != request.user.pk:
        return HttpResponse("You do not have permission to access this payslip.", status=403)

    pdf_buffer = BytesIO()
    document = SimpleDocTemplate(
        pdf_buffer,
        pagesize=A4,
        rightMargin=22 * mm,
        leftMargin=22 * mm,
        topMargin=22 * mm,
        bottomMargin=22 * mm,
        title=f"Payslip {payslip.pay_period}",
        author="NHL Payroll",
    )
    styles = getSampleStyleSheet()
    elements = [
        Paragraph("NHL Payroll", styles["Title"]),
        Paragraph("Employee payslip", styles["Heading2"]),
        Spacer(1, 8 * mm),
    ]
    employee = payslip.employee
    details = [
        ["Employee", f"{employee.First_name} {employee.last_name}"],
        ["Email", employee.email],
        ["Department", employee.department_name.department_name],
        ["Position", employee.position.title],
        ["Pay period", payslip.pay_period],
        ["Payroll run", f"{payslip.payroll.month}/{payslip.payroll.year}"],
    ]
    details_table = Table(details, colWidths=[42 * mm, 110 * mm])
    details_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#E6F3EF")),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#18302D")),
                ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#18302D")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D7E2DE")),
                ("PADDING", (0, 0), (-1, -1), 9),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    amounts = [
        ["Earnings and deductions", "Amount"],
        ["Gross pay", f"{payslip.gross_pay:,.2f}"],
        ["Deductions", f"{payslip.deductions:,.2f}"],
        [
            "Net pay",
            f"{(payslip.net_pay if payslip.net_pay is not None else payslip.gross_pay - payslip.deductions):,.2f}",
        ],
    ]
    amounts_table = Table(amounts, colWidths=[105 * mm, 47 * mm])
    amounts_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#16735D")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#E6F3EF")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D7E2DE")),
                ("ALIGN", (1, 1), (1, -1), "RIGHT"),
                ("PADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    elements.extend(
        [
            details_table,
            Spacer(1, 10 * mm),
            amounts_table,
            Spacer(1, 8 * mm),
            Paragraph("This payslip was generated by NHL Payroll.", styles["Normal"]),
        ]
    )
    document.build(elements)

    response = HttpResponse(pdf_buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="payslip-{payslip.pk}-{payslip.payroll.year}-'
        f'{payslip.payroll.month:02d}.pdf"'
    )
    response["Cache-Control"] = "private, no-store"
    return response

def  sign_up_view(request):
    message = ''
    if request.method == 'POST':
        sign_up_form = UserCreationForm(request.POST)
        if sign_up_form.is_valid():
            sign_up_form.save()
            message = 'Account created successfully! You can now log in.'
            return redirect('login')
    else:
        sign_up_form = UserCreationForm()
    context = {
        'form': sign_up_form,
        'msg': message
    }
    return render(request, 'registration/sign_up.html', context)
