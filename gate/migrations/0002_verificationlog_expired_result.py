from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("gate", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="verificationlog",
            name="result",
            field=models.CharField(
                choices=[
                    ("VALID", "Valid"),
                    ("ALREADY_USED", "Already Used"),
                    ("INVALID", "Invalid"),
                    ("EXPIRED", "Expired"),
                ],
                max_length=20,
            ),
        ),
    ]
