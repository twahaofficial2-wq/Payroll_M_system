from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db.models import Q
from django.utils import timezone
from django.conf import settings

class Department(models.Model):
    department_name = models.CharField(max_length=50)
    summary = models.TextField()
    manager = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="managed_department",
    )

    def __str__(self):
        return f"{self.department_name}"

class Position(models.Model):
    title = models.CharField(max_length=100)
    level = models.CharField(max_length=50)
    department_name = models.ForeignKey(Department,  on_delete=models.CASCADE)
    def __str__(self):
        return f"{self.title}"

class Salary_Scale(models.Model):
    position = models.OneToOneField(Position,on_delete=models.CASCADE)
    entry_level_salary = models.DecimalField(max_digits=10,decimal_places=2)
    junior_level_salary = models.DecimalField(max_digits=10,decimal_places=2)
    senior_level_salary = models.DecimalField(max_digits=10,decimal_places=2)

    def __str__(self):
        return f"{self.position} salary scale"

    def view_salary_scale(self):
        return f"{self.entry_level_salary}"
    def update_salary_Scale(self):
        self.save()

class Employee(models.Model):
    GENDER_CHOICES =[
        ('M','male'),
        ('F','female')
    ]
    First_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    contact = models.CharField(max_length=10,unique=True)
    email = models.EmailField(unique=True)
    department_name = models.ForeignKey(Department,  on_delete=models.CASCADE)
    position = models.ForeignKey(Position, on_delete=models.PROTECT)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="payroll_employee",
    )
    hire_date = models.DateField(default=timezone.localdate)
    age = models.IntegerField()
    gender = models.CharField(max_length=1,choices=GENDER_CHOICES)

    def clean(self):
        super().clean()
        if (
            self.department_name_id
            and self.position_id
            and self.position.department_name_id != self.department_name_id
        ):
            raise ValidationError(
                {"position": "Choose a position from the selected department."}
            )

    def __str__(self):
        return f"{self.First_name} {self.last_name}"
    def view_employee(self):
        return f"NAME:\t{self.First_name}\tLAST NAME:\t{self.last_name}"
    def update_profile(self):
        self.save()

class Payroll(models.Model):
    month = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)]
    )
    year = models.IntegerField(
        validators=[MinValueValidator(1900), MaxValueValidator(9999)]
    )
    status = models.CharField(max_length=20, default='pending')

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(month__gte=1) & Q(month__lte=12),
                name="payroll_month_between_1_and_12",
            ),
            models.CheckConstraint(
                condition=Q(year__gte=1900) & Q(year__lte=9999),
                name="payroll_year_between_1900_and_9999",
            ),
            models.UniqueConstraint(
                fields=["month", "year"],
                name="unique_payroll_period",
            ),
        ]

    def __str__(self):
        return f"{self.month}/{self.year}"

    def view_payroll_details(self):
        return f"MONTH:\t{self.month}\nYEAR:\t{self.year}"

class Payslip(models.Model):
    employee = models.ForeignKey(Employee,  on_delete=models.CASCADE)
    payroll = models.ForeignKey(Payroll,  on_delete=models.CASCADE)
    pay_period = models.CharField(max_length=50)
    gross_pay = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    deductions = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    net_pay =models.DecimalField(max_digits=10,decimal_places=2,blank=True,null=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(gross_pay__gte=0),
                name="payslip_gross_pay_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(deductions__gte=0),
                name="payslip_deductions_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(deductions__lte=models.F("gross_pay")),
                name="payslip_deductions_lte_gross_pay",
            ),
        ]

    def clean(self):
        super().clean()
        if (
            self.gross_pay is not None
            and self.deductions is not None
            and self.deductions > self.gross_pay
        ):
            raise ValidationError(
                {"deductions": "Deductions cannot exceed gross pay."}
            )

    def __str__(self):
        return f"{self.employee.First_name}-{self.pay_period}"

    #def calculate_netpay(self):
    #    self.net_pay = self.gross_pay - self.deductions
    #    return self.net_pay
    #def generate_payslip(self):
    #    self.calculate_netpay()
    #    self.save()

    def save(self, *args, **kwargs):
        self.net_pay = self.gross_pay - self.deductions
        super().save(*args, **kwargs)


class LeaveRequest(models.Model):
    LEAVE_TYPE_CHOICES = [
        ("annual", "Annual leave"),
        ("sick", "Sick leave"),
        ("personal", "Personal leave"),
        ("unpaid", "Unpaid leave"),
        ("other", "Other"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="leave_requests"
    )
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPE_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending"
    )
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-submitted_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(end_date__gte=models.F("start_date")),
                name="leave_end_date_on_or_after_start",
            ),
        ]

    def clean(self):
        super().clean()
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date must be on or after start date."})

    def __str__(self):
        return f"{self.employee} - {self.get_leave_type_display()} ({self.status})"


class EmployeeDataRequest(models.Model):
    REQUEST_TYPE_CHOICES = [
        ("new", "New employee"),
        ("update", "Employee record update"),
        ("profile", "Profile update"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    department = models.ForeignKey(
        Department, on_delete=models.CASCADE, related_name="employee_data_requests"
    )
    employee = models.ForeignKey(
        Employee,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="data_requests",
    )
    account = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pending_employee_data_requests",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="submitted_employee_data_requests",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_employee_data_requests",
    )
    request_type = models.CharField(max_length=20, choices=REQUEST_TYPE_CHOICES)
    proposed_data = models.JSONField()
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending"
    )
    review_note = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-submitted_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["employee"],
                condition=Q(status="pending", employee__isnull=False),
                name="one_pending_employee_data_request",
            ),
        ]

    def __str__(self):
        return f"{self.get_request_type_display()} for {self.department}"


class PayrollCorrectionRequest(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("completed", "Completed"),
    ]

    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="payroll_requests"
    )
    pay_period = models.CharField(max_length=50)
    details = models.TextField()
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending"
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_payroll_correction_requests",
    )
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="processed_payroll_correction_requests",
    )
    review_note = models.TextField(blank=True)
    processing_note = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"{self.employee} - {self.pay_period} ({self.status})"
