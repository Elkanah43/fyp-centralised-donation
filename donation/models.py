from django.db import models


class Donor(models.Model):
    DONOR_TYPES = [
        ("Blood", "Blood"),
        ("Organ", "Organ"),
        ("Blood + Organ", "Blood + Organ"),
    ]
    BLOOD_TYPES = [
        ("O-", "O-"),
        ("O+", "O+"),
        ("A-", "A-"),
        ("A+", "A+"),
        ("B-", "B-"),
        ("B+", "B+"),
        ("AB-", "AB-"),
        ("AB+", "AB+"),
    ]
    STATUSES = [
        ("Available", "Available"),
        ("Contacted", "Contacted"),
        ("Medical Review", "Medical Review"),
    ]

    name = models.CharField(max_length=200)
    donor_type = models.CharField(max_length=30, choices=DONOR_TYPES)
    blood_type = models.CharField(max_length=5, choices=BLOOD_TYPES)
    region = models.CharField(max_length=120)
    phone = models.CharField(max_length=30)
    organs = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=30, choices=STATUSES, default="Available")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class RecipientCase(models.Model):
    PRIORITIES = [
        ("Critical", "Critical"),
        ("High", "High"),
        ("Standard", "Standard"),
    ]
    NEED_TYPES = [("Blood", "Blood"), ("Organ", "Organ")]

    recipient = models.CharField(max_length=200)
    need_type = models.CharField(max_length=20, choices=NEED_TYPES)
    priority = models.CharField(max_length=20, choices=PRIORITIES)
    blood_type = models.CharField(max_length=5)
    organ = models.CharField(max_length=50, blank=True)
    hospital = models.CharField(max_length=200)
    region = models.CharField(max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.recipient


class Appointment(models.Model):
    donor = models.ForeignKey(Donor, on_delete=models.CASCADE, related_name="appointments")
    date = models.DateField()
    time = models.TimeField()
    site = models.CharField(max_length=200)
    purpose = models.CharField(max_length=80)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.donor.name} - {self.date}"


class InventoryItem(models.Model):
    blood_type = models.CharField(max_length=5, unique=True)
    units = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.blood_type}: {self.units}"


class Alert(models.Model):
    LEVELS = [("Critical", "Critical"), ("Notice", "Notice")]

    level = models.CharField(max_length=20, choices=LEVELS)
    title = models.CharField(max_length=200)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title
