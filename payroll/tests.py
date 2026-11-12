from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from .forms import DepartmentForm
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


class AuthenticationTests(TestCase):
    protected_urls = (
        ("home_page", ()),
        ("dashboard_page", ()),
        ("add_employee_page", ()),
        ("edit_employee_page", (1,)),
        ("delete_employee_page", (1,)),
        ("add_department_page", ()),
        ("edit_department_page", (1,)),
        ("delete_department_page", (1,)),
        ("add_position_page", ()),
        ("edit_position_page", (1,)),
        ("delete_position_page", (1,)),
        ("add_salary_scale_page", ()),
        ("edit_salary_scale_page", (1,)),
        ("delete_salary_scale_page", (1,)),
        ("add_payroll_page", ()),
        ("edit_payroll_page", (1,)),
        ("delete_payroll_page", (1,)),
        ("add_payslip_page", ()),
        ("edit_payslip_page", (1,)),
        ("delete_payslip_page", (1,)),
        ("download_payslip_page", (1,)),
        ("employee_profile_page", ()),
        ("employee_payslips_page", ()),
        ("leave_request_page", ()),
        ("staff_leave_requests_page", ()),
        ("manager_employees_page", ()),
        ("manager_leave_requests_page", ()),
        ("manager_payroll_requests_page", ()),
        ("manager_employee_data_requests_page", ()),
        ("staff_payroll_requests_page", ()),
        ("staff_employee_data_requests_page", ()),
        ("employee_payroll_requests_page", ()),
        ("review_leave_request_page", (1,)),
    )

    def test_payroll_pages_redirect_anonymous_users_to_login(self):
        for url_name, args in self.protected_urls:
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name, args=args))
                self.assertRedirects(
                    response,
                    f"{reverse('login')}?next={reverse(url_name, args=args)}",
                )

    def test_landing_login_and_signup_are_public(self):
        for url_name in ("index_page", "login", "sign_up_page"):
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'class="site-footer"')
                self.assertContains(response, "NHL Payroll. All rights reserved.")

    def test_landing_page_stats_come_from_database(self):
        response = self.client.get(reverse("index_page"))
        self.assertEqual(response.context["employee_count"], Employee.objects.count())
        self.assertEqual(response.context["payroll_count"], Payroll.objects.count())
        self.assertEqual(response.context["payslip_count"], Payslip.objects.count())
        self.assertContains(response, "Kaiadmin/assets/img/best_payroll.jpg")
        self.assertContains(response, 'alt="Payroll management workspace')
        self.assertNotContains(response, "100% Secure")
        self.assertNotContains(response, "24/7 Access")

    def test_signup_page_keeps_footer_after_registration_form(self):
        response = self.client.get(reverse("sign_up_page"))
        content = response.content.decode()
        self.assertIn('class="auth-card auth-card-signup"', content)
        self.assertIn('class="auth-form auth-form-signup"', content)
        self.assertLess(content.index("</main>"), content.index('<footer class="site-footer">'))

    def test_theme_toggle_is_available_and_has_accessible_state(self):
        response = self.client.get(reverse("index_page"))
        self.assertContains(response, 'id="theme-toggle"')
        self.assertContains(response, 'aria-label="Switch to dark mode"')
        self.assertContains(response, "localStorage.setItem('payroll-theme', nextTheme)")
        self.assertContains(response, 'html[data-theme="dark"]')
        self.assertContains(response, "linear-gradient(180deg, #0b5cab")
        self.assertContains(response, "#70c5ff")
        self.assertContains(response, "@media (prefers-reduced-motion: reduce)")
        self.assertContains(response, "@keyframes payroll-spin")

    def test_signup_creates_non_staff_user(self):
        response = self.client.post(
            reverse("sign_up_page"),
            {
                "username": "new-payroll-user",
                "password1": "Strong-password-456!",
                "password2": "Strong-password-456!",
            },
        )
        self.assertRedirects(response, reverse("login"))
        user = get_user_model().objects.get(username="new-payroll-user")
        self.assertFalse(user.is_staff)

    def test_regular_user_cannot_access_payroll_pages(self):
        user = get_user_model().objects.create_user(
            username="payroll-user",
            password="Valid-password-123",
        )
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("home_page")).status_code, 200)
        for url_name in ("dashboard_page", "add_employee_page"):
            with self.subTest(url_name=url_name):
                self.assertEqual(self.client.get(reverse(url_name)).status_code, 302)

    def test_employee_portal_shows_only_linked_employees_payslips_read_only(self):
        user = get_user_model().objects.create_user(
            username="employee-user",
            password="Valid-password-123",
        )
        department = Department.objects.create(
            department_name="Staff team",
            summary="Staff",
        )
        position = Position.objects.create(
            title="Staff role",
            level="Junior",
            department_name=department,
        )
        own_employee = Employee.objects.create(
            First_name="Sam",
            last_name="Employee",
            contact="5550001001",
            email="sam@example.com",
            department_name=department,
            position=position,
            user=user,
            age=29,
            gender="M",
        )
        other_employee = Employee.objects.create(
            First_name="Other",
            last_name="Person",
            contact="5550001002",
            email="other@example.com",
            department_name=department,
            position=position,
            age=31,
            gender="F",
        )
        payroll = Payroll.objects.create(month=4, year=2026)
        Payslip.objects.create(
            employee=own_employee,
            payroll=payroll,
            pay_period="April 2026",
            gross_pay=Decimal("2000.00"),
            deductions=Decimal("200.00"),
        )
        Payslip.objects.create(
            employee=other_employee,
            payroll=payroll,
            pay_period="April 2026",
            gross_pay=Decimal("9000.00"),
            deductions=Decimal("100.00"),
        )

        self.client.force_login(user)
        response = self.client.get(reverse("home_page"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Welcome, Sam")
        self.assertContains(response, "--primary: #1479c9")
        self.assertContains(response, "@keyframes employee-water-flow")
        self.assertContains(response, reverse("employee_payslips_page"))
        self.assertContains(response, "data-payslip-download")
        self.assertNotContains(response, "Other Person")
        self.assertNotContains(response, "9000.00")
        self.assertNotContains(response, "edit_employee_page")
        self.assertNotContains(response, "delete_employee_page")
        payslip_history = self.client.get(reverse("employee_payslips_page"))
        self.assertContains(payslip_history, "2000.00")
        self.assertNotContains(payslip_history, "Other Person")
        self.assertNotContains(payslip_history, "9000.00")
        own_pdf = self.client.get(
            reverse("download_payslip_page", args=[own_employee.payslip_set.get().pk])
        )
        self.assertEqual(own_pdf.status_code, 200)
        self.assertEqual(own_pdf["Content-Type"], "application/pdf")
        self.assertTrue(own_pdf.content.startswith(b"%PDF-"))
        self.assertIn("attachment;", own_pdf["Content-Disposition"])
        other_payslip = other_employee.payslip_set.get()
        self.assertEqual(
            self.client.get(
                reverse("download_payslip_page", args=[other_payslip.pk])
            ).status_code,
            403,
        )

    def test_unlinked_regular_account_sees_linking_instructions(self):
        user = get_user_model().objects.create_user(
            username="unlinked-user",
            password="Valid-password-123",
        )
        self.client.force_login(user)
        response = self.client.get(reverse("home_page"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your employee account needs to be linked")
        self.assertContains(response, "employee-sidebar")
        profile_response = self.client.get(
            reverse("employee_profile_page"), follow=True
        )
        self.assertRedirects(profile_response, reverse("home_page"))
        self.assertContains(profile_response, "Employees")

    def test_authenticated_user_is_redirected_away_from_login_page(self):
        user = get_user_model().objects.create_user(
            username="already-signed-in",
            password="Valid-password-123!",
        )
        self.client.force_login(user)
        self.assertRedirects(
            self.client.get(reverse("login")), reverse("home_page")
        )

    def test_staff_user_can_open_payroll_page(self):
        user = get_user_model().objects.create_user(
            username="payroll-staff",
            password="Valid-password-123",
            is_staff=True,
        )
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("home_page")).status_code, 200)
        response = self.client.get(reverse("add_employee_page"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "color: #fff !important")
        self.assertContains(response, ".sidebar .sidebar-logo")
        self.assertContains(response, "display: block !important")

    def test_staff_greeting_shows_username_on_shared_pages(self):
        user = get_user_model().objects.create_user(
            username="admin",
            password="Valid-password-123",
            is_staff=True,
        )
        self.client.force_login(user)
        for url_name in ("home_page", "dashboard_page"):
            with self.subTest(url_name=url_name):
                self.assertContains(
                    self.client.get(reverse(url_name)),
                    "Hi, admin",
                )

    def test_user_can_log_in_and_log_out(self):
        get_user_model().objects.create_user(
            username="payroll-login-user",
            password="Valid-password-123",
        )
        response = self.client.post(
            reverse("login"),
            {"username": "payroll-login-user", "password": "Valid-password-123"},
        )
        self.assertRedirects(response, reverse("home_page"))
        self.assertRedirects(self.client.post(reverse("logout")), reverse("login"))

    def test_invalid_signup_submission_renders_form_errors(self):
        response = self.client.post(reverse("sign_up_page"), {"username": ""})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required")


class PayrollWorkflowTests(TestCase):
    def setUp(self):
        staff = get_user_model().objects.create_user(
            username="payroll-admin",
            password="Valid-password-123",
            is_staff=True,
        )
        self.client.force_login(staff)
        self.department = Department.objects.create(
            department_name="Finance",
            summary="Finance team",
        )
        self.position = Position.objects.create(
            title="Accountant",
            level="Junior",
            department_name=self.department,
        )

    def test_salary_scale_has_a_readable_admin_label(self):
        salary_scale = Salary_Scale.objects.create(
            position=self.position,
            entry_level_salary=Decimal("1000.00"),
            junior_level_salary=Decimal("1500.00"),
            senior_level_salary=Decimal("2000.00"),
        )

        self.assertEqual(str(salary_scale), "Accountant salary scale")

    def make_employee(self, **overrides):
        values = {
            "First_name": "Ari",
            "last_name": "Kim",
            "contact": "1234567890",
            "email": "ari@example.com",
            "department_name": self.department,
            "position": self.position,
            "age": 30,
            "gender": "F",
        }
        values.update(overrides)
        return Employee.objects.create(**values)

    def test_dashboard_summarizes_latest_payroll_period_totals(self):
        employee = self.make_employee()
        older_payroll = Payroll.objects.create(month=12, year=2025)
        latest_payroll = Payroll.objects.create(
            month=1, year=2026, status="paid"
        )
        Payslip.objects.create(
            employee=employee,
            payroll=latest_payroll,
            pay_period="January 2026",
            gross_pay=Decimal("3000.00"),
            deductions=Decimal("300.00"),
        )
        Payslip.objects.create(
            employee=employee,
            payroll=latest_payroll,
            pay_period="January 2026",
            gross_pay=Decimal("2000.00"),
            deductions=Decimal("250.00"),
        )
        Payslip.objects.create(
            employee=employee,
            payroll=older_payroll,
            pay_period="December 2025",
            gross_pay=Decimal("1000.00"),
            deductions=Decimal("100.00"),
        )

        response = self.client.get(reverse("dashboard_page"))

        self.assertEqual(response.context["latest_payroll"], latest_payroll)
        self.assertEqual(
            response.context["current_payroll_totals"],
            {
                "gross_pay": Decimal("5000.00"),
                "deductions": Decimal("550.00"),
                "net_pay": Decimal("4450.00"),
            },
        )
        self.assertContains(response, "1/2026")
        self.assertContains(response, "5000.00")
        self.assertContains(response, "4450.00")
        self.assertContains(response, "2 payslips in this period")
        self.assertContains(response, "Kaiadmin/assets/img/payroll%20(9).jpg")
        self.assertContains(response, "Calculator and financial charts")

    def test_dashboard_shows_empty_payroll_prompt(self):
        response = self.client.get(reverse("dashboard_page"))
        self.assertIsNone(response.context["latest_payroll"])
        self.assertIsNone(response.context["current_payroll_totals"])
        self.assertContains(response, "No payroll periods yet")
        self.assertContains(response, "Kaiadmin/assets/img/undraw/undraw_no_data_qbuo.svg")

    def test_position_edit_uses_position_model(self):
        response = self.client.get(
            reverse("edit_position_page", args=[self.position.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_salary_scale_delete_works_with_post(self):
        scale = Salary_Scale.objects.create(
            position=self.position,
            entry_level_salary="1000.00",
            junior_level_salary="1500.00",
            senior_level_salary="2000.00",
        )
        response = self.client.post(
            reverse("delete_salary_scale_page", args=[scale.pk])
        )
        self.assertRedirects(response, reverse("add_salary_scale_page"))
        self.assertFalse(Salary_Scale.objects.filter(pk=scale.pk).exists())

    def test_staff_can_download_payslip_pdf(self):
        employee = self.make_employee()
        payroll = Payroll.objects.create(month=3, year=2027)
        payslip = Payslip.objects.create(
            employee=employee,
            payroll=payroll,
            pay_period="March 2027",
            gross_pay=Decimal("1000.00"),
            deductions=Decimal("100.00"),
        )
        response = self.client.get(
            reverse("download_payslip_page", args=[payslip.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF-"))
        self.assertIn(
            f'payslip-{payslip.pk}-2027-03.pdf',
            response["Content-Disposition"],
        )

    def test_employee_search_filter_and_pagination(self):
        for index in range(12):
            self.make_employee(
                First_name=f"Search{index}",
                contact=f"123456{index:04d}",
                email=f"search{index}@example.com",
            )
        other_department = Department.objects.create(
            department_name="Other", summary="Other department"
        )
        other_position = Position.objects.create(
            title="Other role", level="Senior", department_name=other_department
        )
        self.make_employee(
            First_name="Needle",
            contact="9999999999",
            email="needle@example.com",
            department_name=other_department,
            position=other_position,
        )

        first_page = self.client.get(reverse("add_employee_page"))
        self.assertEqual(len(first_page.context["employees"]), 10)
        self.assertTrue(first_page.context["employee_page"].has_next())
        second_page = self.client.get(
            reverse("add_employee_page"), {"page": 2}
        )
        self.assertEqual(len(second_page.context["employees"]), 3)

        filtered = self.client.get(
            reverse("add_employee_page"),
            {"q": "Needle", "department": other_department.pk},
        )
        self.assertEqual(filtered.context["employee_page"].paginator.count, 1)
        self.assertEqual(filtered.context["employees"][0].First_name, "Needle")
        self.assertContains(filtered, "Needle")
        self.assertContains(filtered, "Clear")

    def test_payslip_search_payroll_status_filter_and_pagination(self):
        payroll = Payroll.objects.create(month=5, year=2027, status="paid")
        for index in range(12):
            employee = self.make_employee(
                First_name=f"Pay{index}",
                contact=f"222222{index:04d}",
                email=f"pay{index}@example.com",
            )
            Payslip.objects.create(
                employee=employee,
                payroll=payroll,
                pay_period=f"May 2027 {index}",
                gross_pay=Decimal("1000.00"),
                deductions=Decimal("100.00"),
            )
        pending_payroll = Payroll.objects.create(month=6, year=2027)
        pending_employee = self.make_employee(
            First_name="Pending",
            contact="3333333333",
            email="pending@example.com",
        )
        Payslip.objects.create(
            employee=pending_employee,
            payroll=pending_payroll,
            pay_period="June 2027",
            gross_pay=Decimal("1200.00"),
            deductions=Decimal("100.00"),
        )

        first_page = self.client.get(reverse("add_payslip_page"))
        self.assertEqual(len(first_page.context["payslips"]), 10)
        second_page = self.client.get(reverse("add_payslip_page"), {"page": 2})
        self.assertEqual(len(second_page.context["payslips"]), 3)

        filtered = self.client.get(
            reverse("add_payslip_page"),
            {"q": "Pay1", "payroll": payroll.pk, "status": "paid"},
        )
        self.assertEqual(filtered.context["payslip_page"].paginator.count, 3)
        self.assertContains(filtered, "Pay10")
        self.assertContains(filtered, "PDF")
        self.assertTrue(
            all(
                payslip.payroll.status == "paid"
                for payslip in filtered.context["payslips"]
            )
        )

    def test_delete_requires_post_and_get_does_not_delete(self):
        employee = self.make_employee()
        response = self.client.get(
            reverse("delete_employee_page", args=[employee.pk])
        )
        self.assertEqual(response.status_code, 405)
        self.assertTrue(Employee.objects.filter(pk=employee.pk).exists())

    def test_assigned_position_cannot_be_deleted(self):
        employee = self.make_employee()
        response = self.client.post(
            reverse("delete_position_page", args=[self.position.pk]),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Position.objects.filter(pk=self.position.pk).exists())
        self.assertTrue(Employee.objects.filter(pk=employee.pk).exists())
        self.assertContains(response, "assigned to employees")

    def test_department_with_assigned_employee_cannot_be_deleted(self):
        employee = self.make_employee()
        response = self.client.post(
            reverse("delete_department_page", args=[self.department.pk]),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Department.objects.filter(pk=self.department.pk).exists())
        self.assertTrue(Employee.objects.filter(pk=employee.pk).exists())
        self.assertContains(response, "Reassign those employees")

    def test_position_must_belong_to_employee_department(self):
        other_department = Department.objects.create(
            department_name="Operations",
            summary="Operations team",
        )
        other_position = Position.objects.create(
            title="Operator",
            level="Junior",
            department_name=other_department,
        )
        employee = Employee(
            First_name="Ari",
            last_name="Kim",
            contact="1234567890",
            email="invalid-position@example.com",
            department_name=self.department,
            position=other_position,
            age=30,
            gender="F",
        )
        with self.assertRaises(ValidationError):
            employee.full_clean()

    def test_hire_date_is_preserved_when_employee_is_updated(self):
        employee = self.make_employee()
        original_hire_date = employee.hire_date
        employee.last_name = "Updated"
        employee.save()
        employee.refresh_from_db()
        self.assertEqual(employee.hire_date, original_hire_date)

    def test_payroll_form_rejects_invalid_month_and_duplicate_period(self):
        Payroll.objects.create(month=3, year=2026)
        for month, year in ((0, 2027), (13, 2027), (3, 2026)):
            with self.subTest(month=month, year=year):
                response = self.client.post(
                    reverse("add_payroll_page"),
                    {"month": month, "year": year, "status": "pending"},
                )
                self.assertEqual(response.status_code, 200)
                expected_count = 1 if month == 3 else 0
                self.assertEqual(
                    Payroll.objects.filter(month=month, year=year).count(),
                    expected_count,
                )

    def test_payslip_rejects_deductions_above_gross_pay(self):
        employee = self.make_employee()
        payroll = Payroll.objects.create(month=3, year=2027)
        response = self.client.post(
            reverse("add_payslip_page"),
            {
                "employee": employee.pk,
                "payroll": payroll.pk,
                "pay_period": "March 2027",
                "gross_pay": "1000.00",
                "deductions": "1001.00",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Payslip.objects.exists())

    def test_database_rejects_deductions_above_gross_pay(self):
        employee = self.make_employee()
        payroll = Payroll.objects.create(month=3, year=2027)
        with self.assertRaises(ValidationError):
            Payslip(
                employee=employee,
                payroll=payroll,
                pay_period="March 2027",
                gross_pay="1000.00",
                deductions="1001.00",
            ).full_clean()

    def test_landing_page_links_use_named_routes(self):
        response = self.client.get(reverse("index_page"))
        self.assertContains(response, reverse("sign_up_page"))
        self.assertContains(response, reverse("login"))


class EmployeeSelfServiceTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(
            department_name="People", summary="People team"
        )
        self.position = Position.objects.create(
            title="Coordinator", level="Junior", department_name=self.department
        )
        self.user = get_user_model().objects.create_user(
            username="employee-self-service",
            password="Current-password-123!",
            email="self-service@example.com",
        )
        self.employee = Employee.objects.create(
            First_name="Taylor",
            last_name="Jones",
            contact="5551234567",
            email="self-service@example.com",
            department_name=self.department,
            position=self.position,
            user=self.user,
            age=30,
            gender="F",
        )
        self.client.force_login(self.user)

    def test_employee_can_view_and_update_own_contact_profile(self):
        response = self.client.get(reverse("employee_profile_page"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Taylor Jones")
        self.assertContains(response, "People")

        response = self.client.post(
            reverse("employee_profile_page"),
            {"email": "taylor.updated@example.com", "contact": "5557654321"},
        )

        self.assertRedirects(response, reverse("employee_profile_page"))
        self.employee.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(self.employee.email, "taylor.updated@example.com")
        self.assertEqual(self.employee.contact, "5557654321")
        self.assertEqual(self.user.email, self.employee.email)

    def test_employee_can_submit_leave_and_only_sees_own_requests(self):
        other_user = get_user_model().objects.create_user(
            username="another-employee",
            password="Current-password-123!",
        )
        other_employee = Employee.objects.create(
            First_name="Morgan",
            last_name="Lee",
            contact="5551234568",
            email="another@example.com",
            department_name=self.department,
            position=self.position,
            user=other_user,
            age=31,
            gender="M",
        )
        LeaveRequest.objects.create(
            employee=other_employee,
            leave_type="annual",
            start_date="2027-04-10",
            end_date="2027-04-11",
            reason="Personal plans",
        )

        response = self.client.post(
            reverse("leave_request_page"),
            {
                "leave_type": "sick",
                "start_date": "2027-04-12",
                "end_date": "2027-04-13",
                "reason": "Medical appointment",
            },
        )

        self.assertRedirects(response, reverse("leave_request_page"))
        own_request = LeaveRequest.objects.get(employee=self.employee)
        self.assertEqual(own_request.status, "pending")
        self.assertContains(
            self.client.get(reverse("leave_request_page")), "Medical appointment"
        )
        self.assertNotContains(
            self.client.get(reverse("leave_request_page")), "Personal plans"
        )

    def test_leave_request_rejects_end_date_before_start_date(self):
        response = self.client.post(
            reverse("leave_request_page"),
            {
                "leave_type": "annual",
                "start_date": "2027-04-14",
                "end_date": "2027-04-13",
                "reason": "Trip",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(LeaveRequest.objects.exists())
        self.assertContains(response, "End date must be on or after start date.")

    def test_database_rejects_leave_request_with_end_before_start(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                LeaveRequest.objects.create(
                    employee=self.employee,
                    leave_type="annual",
                    start_date="2027-04-14",
                    end_date="2027-04-13",
                    reason="Trip",
                )

    def test_employee_can_change_password(self):
        response = self.client.post(
            reverse("password_change"),
            {
                "old_password": "Current-password-123!",
                "new_password1": "New-employee-password-456!",
                "new_password2": "New-employee-password-456!",
            },
        )
        self.assertRedirects(response, reverse("password_change_done"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("New-employee-password-456!"))

    def test_staff_can_review_a_leave_request_once(self):
        leave_request = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type="annual",
            start_date="2027-05-01",
            end_date="2027-05-03",
            reason="Family trip",
        )
        staff_user = get_user_model().objects.create_user(
            username="leave-reviewer",
            password="Staff-password-123!",
            is_staff=True,
        )
        self.client.force_login(staff_user)

        response = self.client.post(
            reverse("review_leave_request_page", args=[leave_request.pk]),
            {"decision": "approved"},
        )

        self.assertRedirects(response, reverse("staff_leave_requests_page"))
        leave_request.refresh_from_db()
        self.assertEqual(leave_request.status, "approved")

        self.client.post(
            reverse("review_leave_request_page", args=[leave_request.pk]),
            {"decision": "rejected"},
        )
        leave_request.refresh_from_db()
        self.assertEqual(leave_request.status, "approved")

    def test_employee_cannot_review_leave_requests(self):
        leave_request = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type="annual",
            start_date="2027-05-01",
            end_date="2027-05-02",
            reason="Family plans",
        )
        response = self.client.post(
            reverse("review_leave_request_page", args=[leave_request.pk]),
            {"decision": "approved"},
        )
        self.assertEqual(response.status_code, 403)
        leave_request.refresh_from_db()
        self.assertEqual(leave_request.status, "pending")

    def test_staff_can_link_an_existing_account_from_employee_edit(self):
        unlinked_user = get_user_model().objects.create_user(
            username="existing-payroll-login",
            password="Existing-password-123!",
            email="old-address@example.com",
        )
        staff_user = get_user_model().objects.create_user(
            username="employee-linker",
            password="Staff-password-123!",
            is_staff=True,
        )
        self.client.force_login(staff_user)

        response = self.client.post(
            reverse("edit_employee_page", args=[self.employee.pk]),
            {
                "First_name": self.employee.First_name,
                "last_name": self.employee.last_name,
                "contact": self.employee.contact,
                "email": self.employee.email,
                "department_name": self.department.pk,
                "position": self.position.pk,
                "hire_date": self.employee.hire_date.isoformat(),
                "age": self.employee.age,
                "gender": self.employee.gender,
                "user": unlinked_user.pk,
            },
        )

        self.assertRedirects(response, reverse("add_employee_page"))
        self.employee.refresh_from_db()
        unlinked_user.refresh_from_db()
        self.assertEqual(self.employee.user, unlinked_user)
        self.assertEqual(unlinked_user.email, self.employee.email)

    def test_unlinked_employee_pages_redirect_to_overview_instead_of_404(self):
        unlinked_user = get_user_model().objects.create_user(
            username="not-linked-yet",
            password="Unlinked-password-123!",
        )
        self.client.force_login(unlinked_user)
        for url_name in (
            "employee_profile_page",
            "employee_payslips_page",
            "leave_request_page",
        ):
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name))
                self.assertRedirects(response, reverse("home_page"))

    def test_staff_add_employee_creates_login_and_links_account(self):
        staff_user = get_user_model().objects.create_user(
            username="employee-creator",
            password="Staff-password-123!",
            is_staff=True,
        )
        self.client.force_login(staff_user)
        response = self.client.post(
            reverse("add_employee_page"),
            {
                "First_name": "Casey",
                "last_name": "Reed",
                "contact": "5557654322",
                "email": "casey@example.com",
                "department_name": self.department.pk,
                "position": self.position.pk,
                "hire_date": "2026-02-01",
                "age": 28,
                "gender": "F",
                "username": "casey.reed",
                "password1": "Strong-casey-password-456!",
                "password2": "Strong-casey-password-456!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Employee and login account added successfully.")
        created_employee = Employee.objects.get(email="casey@example.com")
        self.assertEqual(created_employee.user.get_username(), "casey.reed")
        self.assertEqual(created_employee.user.email, created_employee.email)
        self.client.logout()
        self.assertTrue(
            self.client.login(
                username="casey.reed", password="Strong-casey-password-456!"
            )
        )
        self.assertEqual(self.client.get(reverse("home_page")).status_code, 200)


class DepartmentManagerTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.department = Department.objects.create(
            department_name="Operations", summary="Operations team"
        )
        self.position = Position.objects.create(
            title="Coordinator", level="Junior", department_name=self.department
        )
        self.manager_user = user_model.objects.create_user(
            username="ops-manager",
            password="Manager-password-123!",
            email="manager@example.com",
        )
        self.manager = Employee.objects.create(
            First_name="Alex",
            last_name="Manager",
            contact="5553300001",
            email="manager@example.com",
            department_name=self.department,
            position=self.position,
            user=self.manager_user,
            age=38,
            gender="M",
        )
        self.department.manager = self.manager_user
        self.department.save(update_fields=["manager"])
        self.employee_user = user_model.objects.create_user(
            username="ops-employee",
            password="Employee-password-123!",
            email="employee@example.com",
        )
        self.employee = Employee.objects.create(
            First_name="Jamie",
            last_name="Employee",
            contact="5553300002",
            email="employee@example.com",
            department_name=self.department,
            position=self.position,
            user=self.employee_user,
            age=29,
            gender="F",
        )
        self.other_department = Department.objects.create(
            department_name="Finance", summary="Finance team"
        )
        self.other_position = Position.objects.create(
            title="Analyst", level="Senior", department_name=self.other_department
        )
        self.other_employee = Employee.objects.create(
            First_name="Robin",
            last_name="Other",
            contact="5553300003",
            email="other@example.com",
            department_name=self.other_department,
            position=self.other_position,
            age=32,
            gender="F",
        )
        self.client.force_login(self.manager_user)

    def test_manager_assignment_is_limited_to_linked_department_employees(self):
        department_form = DepartmentForm(instance=self.department)
        allowed_managers = department_form.fields["manager"].queryset
        self.assertIn(self.manager_user, allowed_managers)
        self.assertNotIn(self.other_employee.user, allowed_managers)

    def test_manager_sees_only_department_employees_without_pay_information(self):
        payroll = Payroll.objects.create(month=5, year=2026)
        Payslip.objects.create(
            employee=self.employee,
            payroll=payroll,
            pay_period="May 2026",
            gross_pay=Decimal("98765.00"),
            deductions=Decimal("100.00"),
        )

        response = self.client.get(reverse("manager_employees_page"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Jamie Employee")
        self.assertNotContains(response, "Robin Other")
        self.assertNotContains(response, "98765.00")
        self.assertEqual(
            self.client.get(reverse("dashboard_page")).status_code, 302
        )

    def test_manager_can_review_department_leave_only(self):
        team_request = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type="annual",
            start_date="2027-06-01",
            end_date="2027-06-02",
            reason="Family plans",
        )
        other_request = LeaveRequest.objects.create(
            employee=self.other_employee,
            leave_type="annual",
            start_date="2027-06-03",
            end_date="2027-06-04",
            reason="Other team leave",
        )
        own_request = LeaveRequest.objects.create(
            employee=self.manager,
            leave_type="personal",
            start_date="2027-06-05",
            end_date="2027-06-05",
            reason="Manager leave",
        )

        response = self.client.get(reverse("manager_leave_requests_page"))
        self.assertContains(response, "Family plans")
        self.assertNotContains(response, "Other team leave")

        own_review = self.client.post(
            reverse("manager_review_leave_request_page", args=[own_request.pk]),
            {"decision": "approved"},
        )
        self.assertEqual(own_review.status_code, 403)
        cross_department_review = self.client.post(
            reverse("manager_review_leave_request_page", args=[other_request.pk]),
            {"decision": "approved"},
        )
        self.assertEqual(cross_department_review.status_code, 403)
        self.client.post(
            reverse("manager_review_leave_request_page", args=[team_request.pk]),
            {"decision": "approved"},
        )
        team_request.refresh_from_db()
        self.assertEqual(team_request.status, "approved")

    def test_payroll_correction_is_scoped_and_staff_processes_approval(self):
        payroll_request = PayrollCorrectionRequest.objects.create(
            employee=self.employee,
            pay_period="May 2026",
            details="Please review a missing allowance entry.",
        )
        other_request = PayrollCorrectionRequest.objects.create(
            employee=self.other_employee,
            pay_period="May 2026",
            details="Other department request.",
        )
        PayrollCorrectionRequest.objects.create(
            employee=self.manager,
            pay_period="May 2026",
            details="Manager self-request.",
        )

        response = self.client.get(reverse("manager_payroll_requests_page"))
        self.assertContains(response, "missing allowance entry")
        self.assertNotContains(response, "Other department request")
        self.assertNotContains(response, "Manager self-request.")
        self.assertNotContains(response, "98765.00")
        self.assertEqual(
            self.client.post(
                reverse("review_payroll_request_page", args=[other_request.pk]),
                {"decision": "approved"},
            ).status_code,
            404,
        )
        self.client.post(
            reverse("review_payroll_request_page", args=[payroll_request.pk]),
            {"decision": "approved", "review_note": "Forward to payroll."},
        )
        payroll_request.refresh_from_db()
        self.assertEqual(payroll_request.status, "approved")
        self.assertEqual(payroll_request.reviewed_by, self.manager_user)

        staff_user = get_user_model().objects.create_user(
            username="payroll-processor",
            password="Processor-password-123!",
            is_staff=True,
        )
        self.client.force_login(staff_user)
        self.assertContains(
            self.client.get(reverse("staff_payroll_requests_page")),
            "missing allowance entry",
        )
        self.client.post(
            reverse("complete_payroll_request_page", args=[payroll_request.pk]),
            {"review_note": "Checked and corrected."},
        )
        payroll_request.refresh_from_db()
        self.assertEqual(payroll_request.status, "completed")
        self.assertEqual(payroll_request.reviewed_by, self.manager_user)
        self.assertEqual(payroll_request.processed_by, staff_user)

    def test_employee_profile_changes_wait_for_manager_approval(self):
        self.client.force_login(self.employee_user)
        response = self.client.post(
            reverse("employee_profile_page"),
            {"email": "jamie.updated@example.com", "contact": "5553300099"},
        )
        self.assertRedirects(response, reverse("employee_profile_page"))
        request = EmployeeDataRequest.objects.get(employee=self.employee)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.email, "employee@example.com")

        self.client.force_login(self.manager_user)
        review_page = self.client.get(
            reverse("manager_employee_data_requests_page")
        )
        self.assertContains(review_page, "employee@example.com")
        self.assertContains(review_page, "jamie.updated@example.com")
        response = self.client.post(
            reverse("review_employee_data_request_page", args=[request.pk]),
            {"decision": "approved"},
        )
        self.assertRedirects(
            response, reverse("manager_employee_data_requests_page")
        )
        self.employee.refresh_from_db()
        self.employee_user.refresh_from_db()
        request.refresh_from_db()
        self.assertEqual(request.status, "approved")
        self.assertEqual(self.employee.email, "jamie.updated@example.com")
        self.assertEqual(self.employee.contact, "5553300099")
        self.assertEqual(self.employee_user.email, self.employee.email)

    def test_staff_employee_record_changes_wait_for_manager_approval(self):
        staff_user = get_user_model().objects.create_user(
            username="employee-editor",
            password="Editor-password-123!",
            is_staff=True,
        )
        self.client.force_login(staff_user)
        response = self.client.post(
            reverse("edit_employee_page", args=[self.employee.pk]),
            {
                "First_name": self.employee.First_name,
                "last_name": self.employee.last_name,
                "contact": "5553300088",
                "email": "jamie.changed@example.com",
                "department_name": self.department.pk,
                "position": self.position.pk,
                "hire_date": self.employee.hire_date,
                "age": self.employee.age,
                "gender": self.employee.gender,
                "user": self.employee_user.pk,
            },
        )
        self.assertRedirects(response, reverse("add_employee_page"))
        data_request = EmployeeDataRequest.objects.get(employee=self.employee)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.email, "employee@example.com")

        self.client.force_login(self.manager_user)
        self.client.post(
            reverse("review_employee_data_request_page", args=[data_request.pk]),
            {"decision": "approved"},
        )
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.email, "jamie.changed@example.com")
        self.assertEqual(self.employee.contact, "5553300088")

    def test_manager_cannot_approve_own_profile_request_but_staff_can(self):
        self.client.post(
            reverse("employee_profile_page"),
            {"email": "manager.updated@example.com", "contact": "5553300098"},
        )
        data_request = EmployeeDataRequest.objects.get(employee=self.manager)
        response = self.client.post(
            reverse("review_employee_data_request_page", args=[data_request.pk]),
            {"decision": "approved"},
        )
        self.assertEqual(response.status_code, 403)

        staff_user = get_user_model().objects.create_user(
            username="data-approver",
            password="Approver-password-123!",
            is_staff=True,
        )
        self.client.force_login(staff_user)
        self.assertContains(
            self.client.get(reverse("staff_employee_data_requests_page")),
            "manager.updated@example.com",
        )
        self.client.post(
            reverse("review_employee_data_request_page", args=[data_request.pk]),
            {"decision": "approved"},
        )
        self.manager.refresh_from_db()
        self.assertEqual(self.manager.email, "manager.updated@example.com")

    def test_manager_cannot_approve_transfer_out_of_their_department(self):
        staff_user = get_user_model().objects.create_user(
            username="transfer-requester",
            password="Requester-password-123!",
            is_staff=True,
        )
        request = EmployeeDataRequest.objects.create(
            department=self.department,
            employee=self.employee,
            requested_by=staff_user,
            request_type="update",
            proposed_data={
                "First_name": self.employee.First_name,
                "last_name": self.employee.last_name,
                "contact": self.employee.contact,
                "email": self.employee.email,
                "department_name": self.other_department.pk,
                "position": self.other_position.pk,
                "hire_date": self.employee.hire_date.isoformat(),
                "age": self.employee.age,
                "gender": self.employee.gender,
                "user_id": self.employee_user.pk,
            },
        )

        response = self.client.post(
            reverse("review_employee_data_request_page", args=[request.pk]),
            {"decision": "approved"},
        )

        self.assertRedirects(
            response, reverse("manager_employee_data_requests_page")
        )
        request.refresh_from_db()
        self.employee.refresh_from_db()
        self.assertEqual(request.status, "pending")
        self.assertEqual(self.employee.department_name, self.department)

    def test_rejecting_new_employee_request_removes_inactive_login(self):
        staff_user = get_user_model().objects.create_user(
            username="rejected-account-requester",
            password="Rejected-request-password-123!",
            is_staff=True,
        )
        inactive_user = get_user_model().objects.create_user(
            username="rejected-pending-account",
            password="Rejected-account-password-123!",
            is_active=False,
        )
        request = EmployeeDataRequest.objects.create(
            department=self.department,
            account=inactive_user,
            requested_by=staff_user,
            request_type="new",
            proposed_data={},
        )

        self.client.post(
            reverse("review_employee_data_request_page", args=[request.pk]),
            {"decision": "rejected"},
        )

        request.refresh_from_db()
        self.assertEqual(request.status, "rejected")
        self.assertIsNone(request.account_id)
        self.assertFalse(
            get_user_model().objects.filter(pk=inactive_user.pk).exists()
        )

    def test_staff_new_employee_account_is_inactive_until_manager_approval(self):
        staff_user = get_user_model().objects.create_user(
            username="employee-creator-manager-test",
            password="Creator-password-123!",
            is_staff=True,
        )
        self.client.force_login(staff_user)
        response = self.client.post(
            reverse("add_employee_page"),
            {
                "First_name": "Casey",
                "last_name": "Pending",
                "contact": "5553300004",
                "email": "casey.pending@example.com",
                "department_name": self.department.pk,
                "position": self.position.pk,
                "hire_date": "2026-03-01",
                "age": 27,
                "gender": "F",
                "username": "casey.pending",
                "password1": "Strong-casey-pending-password-456!",
                "password2": "Strong-casey-pending-password-456!",
            },
        )
        self.assertContains(response, "login stays inactive until approved")
        pending = EmployeeDataRequest.objects.get(
            request_type="new", account__username="casey.pending"
        )
        pending.account.refresh_from_db()
        self.assertFalse(pending.account.is_active)
        self.assertFalse(Employee.objects.filter(email="casey.pending@example.com").exists())

        self.client.force_login(self.manager_user)
        self.client.post(
            reverse("review_employee_data_request_page", args=[pending.pk]),
            {"decision": "approved"},
        )
        pending.refresh_from_db()
        pending.account.refresh_from_db()
        approved_employee = Employee.objects.get(email="casey.pending@example.com")
        self.assertEqual(pending.status, "approved")
        self.assertTrue(pending.account.is_active)
        self.assertEqual(approved_employee.user, pending.account)

    def test_employee_account_cannot_open_manager_pages(self):
        self.client.force_login(self.employee_user)
        for route in (
            "manager_employees_page",
            "manager_leave_requests_page",
            "manager_payroll_requests_page",
            "manager_employee_data_requests_page",
        ):
            with self.subTest(route=route):
                self.assertEqual(self.client.get(reverse(route)).status_code, 403)
