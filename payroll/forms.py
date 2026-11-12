from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.forms import ModelForm
from django import forms
from .models import (
    Department,
    Employee,
    PayrollCorrectionRequest,
    LeaveRequest,
    Payroll,
    Payslip,
    Position,
    Salary_Scale,
)

class EmployeeForm(ModelForm):
    username = forms.CharField(
        max_length=150,
        label="Login username",
        help_text="The employee will use this username to sign in.",
    )
    password1 = forms.CharField(
        label="Initial password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    password2 = forms.CharField(
        label="Confirm temporary password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    class Meta:
        model = Employee
        fields = (
            "First_name",
            "last_name",
            "contact",
            "email",
            "department_name",
            "position",
            "hire_date",
            "age",
            "gender",
        )

    def __init__(self, *args, include_account=True, **kwargs):
        super().__init__(*args, **kwargs)
        if not include_account:
            self.fields.pop("username")
            self.fields.pop("password1")
            self.fields.pop("password2")
            user_model = get_user_model()
            available_users = user_model.objects.filter(
                Q(payroll_employee__isnull=True)
            ).order_by(user_model.USERNAME_FIELD)
            if self.instance.pk and self.instance.user_id:
                available_users = user_model.objects.filter(
                    Q(payroll_employee__isnull=True) | Q(pk=self.instance.user_id)
                ).order_by(user_model.USERNAME_FIELD)
            self.fields["user"] = forms.ModelChoiceField(
                queryset=available_users,
                required=False,
                label="Employee login account",
                help_text=(
                    "Link an existing account to this employee. Linked accounts "
                    "can access this employee's private payroll information."
                ),
            )
        else:
            user_model = get_user_model()
            self.fields["username"].validators = user_model._meta.get_field(
                user_model.USERNAME_FIELD
            ).validators

    def clean_username(self):
        username = self.cleaned_data["username"]
        user_model = get_user_model()
        if user_model.objects.filter(
            **{f"{user_model.USERNAME_FIELD}__iexact": username}
        ).exists():
            raise ValidationError("This username is already in use.")
        return username

    def clean(self):
        cleaned_data = super().clean()
        if "password1" not in self.fields:
            return cleaned_data

        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "The passwords do not match.")
        elif password2:
            user_model = get_user_model()
            user = user_model(
                **{
                    user_model.USERNAME_FIELD: cleaned_data.get("username"),
                    "email": cleaned_data.get("email", ""),
                }
            )
            try:
                password_validation.validate_password(password2, user)
            except ValidationError as error:
                self.add_error("password2", error)
        return cleaned_data


class EmployeeProfileForm(ModelForm):
    class Meta:
        model = Employee
        fields = ("email", "contact")


class LeaveRequestForm(ModelForm):
    class Meta:
        model = LeaveRequest
        fields = ("leave_type", "start_date", "end_date", "reason")
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "reason": forms.Textarea(attrs={"rows": 3}),
        }

class PayrollCorrectionRequestForm(ModelForm):
    class Meta:
        model = PayrollCorrectionRequest
        fields = ("pay_period", "details")
        widgets = {
            "details": forms.Textarea(attrs={"rows": 4}),
        }
        help_texts = {
            "details": (
                "Describe the issue without including bank details or passwords. "
                "Your department manager will review the request."
            ),
        }

class DepartmentForm(ModelForm):
    class Meta:
        model = Department
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        user_model = get_user_model()
        manager_accounts = user_model.objects.none()
        if self.instance.pk:
            manager_accounts = user_model.objects.filter(
                is_staff=False,
                is_active=True,
                managed_department__isnull=True,
                payroll_employee__department_name_id=self.instance.pk,
            ).order_by(user_model.USERNAME_FIELD)
            if self.instance.manager_id:
                manager_accounts = user_model.objects.filter(
                    Q(pk=self.instance.manager_id) | Q(pk__in=manager_accounts)
                ).order_by(user_model.USERNAME_FIELD)
        self.fields["manager"].queryset = manager_accounts
        self.fields["manager"].required = False
        self.fields["manager"].label = "Department manager account"
        self.fields["manager"].help_text = (
            "Only linked employee accounts in this department can be assigned."
        )

    def clean_manager(self):
        manager = self.cleaned_data.get("manager")
        if manager and (
            manager.is_staff
            or not manager.is_active
            or not Employee.objects.filter(
                user=manager, department_name=self.instance
            ).exists()
        ):
            raise ValidationError(
                "Choose a non-staff login linked to an employee in this department."
            )
        return manager

class PositionForm(ModelForm):
    class Meta:
        model = Position
        fields ='__all__'

class Salary_ScaleForm(ModelForm):
    class Meta:
        model = Salary_Scale
        fields ='__all__'

class PayrollForm(ModelForm):
    class Meta:
        model = Payroll
        fields ='__all__'

class PayslipForm(ModelForm):
    class Meta:
        model = Payslip
        fields ='__all__'
        widgets = {
            'net_pay':forms.NumberInput(attrs={'readonly':'readonly'})
        }
