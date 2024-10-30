from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from .models import LoginModel,ClaimModel,PatientModel

class LoginSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoginModel
        fields = '__all__'
        extra_kwargs = {'password': {'write_only': True}}
    def create(self, validated_data):
        user = LoginModel(
            username=validated_data['username'],
            password=make_password(validated_data['password'])
        )
        user.save()
        return user

class PatientSerializer(serializers.ModelSerializer):
    class Meta:
        model = PatientModel
        fields = '__all__'

class ClaimSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClaimModel
        fields = '__all__'

