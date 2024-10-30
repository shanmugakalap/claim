from django.db import models
from django.contrib.auth.hashers import make_password


class LoginModel(models.Model):
    userid = models.AutoField(primary_key=True)
    username = models.CharField(max_length=150, unique=True)
    password = models.CharField(max_length=150)

    def save(self, *args, **kwargs):
        # Ensure password is hashed before saving
        if not self.password.startswith('pbkdf2_sha256$'):  # Avoid rehashing
            self.password = make_password(self.password)
        super(LoginModel, self).save(*args, **kwargs)

    def __str__(self):
        return self.username

class PatientModel(models.Model):
    patient_id = models.AutoField(primary_key=True)
    patient_name = models.CharField(max_length=150)
    patient_address = models.TextField()
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    claim_id = models.ForeignKey('ClaimModel', on_delete=models.CASCADE, related_name="patients",blank=True, null=True)
    type_of_plan = models.CharField(max_length=100)

    def __str__(self):
        return str(self.patient_id)

class ClaimModel(models.Model):
    claim_id = models.AutoField(primary_key=True)
    patient_id = models.ForeignKey('PatientModel', on_delete=models.CASCADE, related_name="claims")
    claim_status = models.CharField(max_length=100)
    disease_name = models.CharField(max_length=100)
    date_of_service = models.DateField()
    treatment_given = models.TextField()
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    lab_test = models.CharField(max_length=100, blank=True, null=True)
    hospital_name = models.CharField(max_length=200)
    hospital_address = models.TextField()
    hospital_city = models.CharField(max_length=100)
    hospital_state = models.CharField(max_length=100)
    hospital_pincode = models.CharField(max_length=10)
    last_timestamp = models.DateTimeField(auto_now=True)
    created_timestamp = models.DateTimeField(auto_now_add=True)
    isFinalized = models.BooleanField(default=False)

    def __str__(self):
        return str(self.claim_id)
        #return f"Claim {self.claim_id}"



