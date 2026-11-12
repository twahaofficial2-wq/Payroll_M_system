from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models
import django.db.models.deletion
from django.utils import timezone


def migrate_employee_positions(apps, schema_editor):
    Employee = apps.get_model("payroll", "Employee")
    Position = apps.get_model("payroll", "Position")
    database = schema_editor.connection.alias

    for employee in Employee.objects.using(database).all().iterator():
        title = employee.position_text
        position = (
            Position.objects.using(database)
            .filter(
                title__iexact=title,
                department_name_id=employee.department_name_id,
            )
            .first()
        )
        if position is None:
            position = Position.objects.using(database).create(
                title=title,
                level="Unspecified",
                department_name_id=employee.department_name_id,
            )
        employee.position_relation_id = position.pk
        employee.save(using=database, update_fields=["position_relation"])


def reverse_employee_positions(apps, schema_editor):
    Employee = apps.get_model("payroll", "Employee")
    database = schema_editor.connection.alias
    for employee in Employee.objects.using(database).select_related(
        "position_relation"
    ).iterator():
        employee.position_text = employee.position_relation.title
        employee.save(using=database, update_fields=["position_text"])


class Migration(migrations.Migration):
    dependencies = [
        ("payroll", "0002_alter_employee_contact_alter_employee_email_and_more"),
    ]

    operations = [
        migrations.RenameField(
            model_name="employee",
            old_name="position",
            new_name="position_text",
        ),
        migrations.AddField(
            model_name="employee",
            name="position_relation",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="payroll.position",
            ),
        ),
        migrations.RunPython(
            migrate_employee_positions,
            reverse_employee_positions,
        ),
        migrations.RemoveField(
            model_name="employee",
            name="position_text",
        ),
        migrations.RenameField(
            model_name="employee",
            old_name="position_relation",
            new_name="position",
        ),
        migrations.AlterField(
            model_name="employee",
            name="position",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                to="payroll.position",
            ),
        ),
        migrations.AlterField(
            model_name="employee",
            name="hire_date",
            field=models.DateField(default=timezone.localdate),
        ),
        migrations.AlterField(
            model_name="payroll",
            name="month",
            field=models.IntegerField(
                validators=[
                    MinValueValidator(1),
                    MaxValueValidator(12),
                ]
            ),
        ),
        migrations.AlterField(
            model_name="payroll",
            name="year",
            field=models.IntegerField(
                validators=[
                    MinValueValidator(1900),
                    MaxValueValidator(9999),
                ]
            ),
        ),
        migrations.AlterField(
            model_name="payslip",
            name="gross_pay",
            field=models.DecimalField(
                decimal_places=2,
                max_digits=10,
                validators=[MinValueValidator(0)],
            ),
        ),
        migrations.AlterField(
            model_name="payslip",
            name="deductions",
            field=models.DecimalField(
                decimal_places=2,
                max_digits=10,
                validators=[MinValueValidator(0)],
            ),
        ),
        migrations.AddConstraint(
            model_name="payroll",
            constraint=models.CheckConstraint(
                condition=models.Q(month__gte=1) & models.Q(month__lte=12),
                name="payroll_month_between_1_and_12",
            ),
        ),
        migrations.AddConstraint(
            model_name="payroll",
            constraint=models.CheckConstraint(
                condition=models.Q(year__gte=1900) & models.Q(year__lte=9999),
                name="payroll_year_between_1900_and_9999",
            ),
        ),
        migrations.AddConstraint(
            model_name="payroll",
            constraint=models.UniqueConstraint(
                fields=("month", "year"),
                name="unique_payroll_period",
            ),
        ),
        migrations.AddConstraint(
            model_name="payslip",
            constraint=models.CheckConstraint(
                condition=models.Q(gross_pay__gte=0),
                name="payslip_gross_pay_nonnegative",
            ),
        ),
        migrations.AddConstraint(
            model_name="payslip",
            constraint=models.CheckConstraint(
                condition=models.Q(deductions__gte=0),
                name="payslip_deductions_nonnegative",
            ),
        ),
        migrations.AddConstraint(
            model_name="payslip",
            constraint=models.CheckConstraint(
                condition=models.Q(deductions__lte=models.F("gross_pay")),
                name="payslip_deductions_lte_gross_pay",
            ),
        ),
    ]
