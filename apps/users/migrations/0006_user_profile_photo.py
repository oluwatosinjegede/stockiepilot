from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0005_user_is_affiliate"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="profile_photo",
            field=models.FileField(blank=True, null=True, upload_to="profile_photos/"),
        ),
    ]
