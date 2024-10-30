from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from .models import LoginModel, PatientModel, ClaimModel
from .serializers import LoginSerializer, PatientSerializer, ClaimSerializer
from rest_framework import generics, status
from rest_framework.response import Response
from django.contrib.auth import authenticate
from rest_framework.permissions import AllowAny
from django.contrib.auth.hashers import check_password
import os
import json
from django.http import JsonResponse
from django.conf import settings
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload,MediaIoBaseDownload
from django.utils.dateparse import parse_datetime
from datetime import datetime
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

# Define the base class with common create logic
class BulkCreate(generics.ListCreateAPIView):
    def create(self, request, *args, **kwargs):
        if isinstance(request.data, list):
            serializer = self.get_serializer(data=request.data, many=True)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        # single-object creation
        return super().create(request, *args, **kwargs)

class LoginCreateView(BulkCreate):
    queryset = LoginModel.objects.all()
    serializer_class = LoginSerializer

class LoginView(generics.GenericAPIView):
    serializer_class = LoginSerializer
    #permission_classes = [AllowAny]  # Allow unauthenticated users to access this view

    def post(self, request, *args, **kwargs):
        username = request.data.get('username')
        password = request.data.get('password')
        #user = authenticate(username=username, password=password)

        try:
            user = LoginModel.objects.get(username=username)
            if check_password(password, user.password):
                return Response({'message': 'Login successful', 'username': username}, status=status.HTTP_200_OK)
            else:
                return Response({'error': 'Invalid credentials'}, status=status.HTTP_400_BAD_REQUEST)
        except LoginModel.DoesNotExist:
            return Response({'error': 'Invalid credentials'}, status=status.HTTP_400_BAD_REQUEST)

class PatientCreateView(BulkCreate):
    queryset = PatientModel.objects.all()
    serializer_class = PatientSerializer

class ClaimCreateView(BulkCreate):
    queryset = ClaimModel.objects.all()
    serializer_class = ClaimSerializer

class ClaimDetailsView(generics.RetrieveUpdateDestroyAPIView):
    queryset = ClaimModel.objects.all()
    serializer_class = ClaimSerializer
    lookup_field = 'claim_id'  # Use `claim_id` as the lookup field in URLs

    def retrieve(self, request, *args, **kwargs):
        # Retrieve the claim object based on claim_id using get_object
        claim = self.get_object()  # Retrieve the claim using the default method
        
        # Fetch the associated patient using claim's patient_id
        try:
            patient = PatientModel.objects.get(patient_id=claim.patient_id.patient_id)  # Get the patient details
            claim_serializer = ClaimSerializer(claim)
            patient_serializer = PatientSerializer(patient)

            return Response({
                'claim': claim_serializer.data,
                'patient': patient_serializer.data,
            })
        except PatientModel.DoesNotExist:
            return Response({'error': 'Patient not found'}, status=status.HTTP_404_NOT_FOUND)

    def update(self, request, *args, **kwargs):
        claim = self.get_object()  # Retrieve the claim instance
        patient = get_object_or_404(PatientModel, patient_id=claim.patient_id.patient_id)  # Get the associated patient

        # Deserialize request data
        claim_serializer = ClaimSerializer(claim, data=request.data, partial=True)

        if claim_serializer.is_valid():
            
            # Update claim only if is_Finalized is True
            if request.data.get('is_Finalized', False):
                claim_serializer.save()
            else:
                claim_serializer.save()  # Save without modifying the total amount if not finalized

            return Response(claim_serializer.data, status=status.HTTP_200_OK)

        return Response(claim_serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class GoogleDriveView(generics.GenericAPIView):
    SERVICE_ACCOUNT_FILE = os.path.join(settings.BASE_DIR, 'claim_app', 'service_account', 'service-account-file.json')
    SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

    def get(self, request):
        if not os.path.exists(self.SERVICE_ACCOUNT_FILE):
            return JsonResponse({"error": "Service account file does not exist"}, status=404)

        try:
            # Authenticate with the service account
            credentials = service_account.Credentials.from_service_account_file(
                self.SERVICE_ACCOUNT_FILE,
                scopes=self.SCOPES
            )
            service = build('drive', 'v3', credentials=credentials)

            # Search for `claim_new.json` in Google Drive
            results = service.files().list(q="name='claim_new.json'", fields="files(id)").execute()
            items = results.get('files', [])
            print(f"Items found: {items}")  # Debug log

            if not items:
                return JsonResponse({"error": "claim_new.json not found in Google Drive"}, status=404)

            # Get file ID and download content
            file_id = items[0]['id']
            request_media = service.files().get_media(fileId=file_id)
            data = request_media.execute()

            # Ensure data is not empty before decoding
            if not data:
                return JsonResponse({"error": "No data returned from the file"}, status=404)

            print(f"Raw data: {data}")  # Debug log
            claims_data = json.loads(data.decode('utf-8'))

            if isinstance(claims_data, list):
                for claim in claims_data:
                    if isinstance(claim, dict):  # Ensure each item is a dict
                        patient_id = claim.get('patient_id')
                        claim_id = claim.get('claim_id')
                        claim_status = claim.get('claim_status')
                        try:
                            patient = PatientModel.objects.get(patient_id=patient_id)
                            # Check if the claim_id already exists
                            if ClaimModel.objects.filter(claim_id=claim_id).exists():
                                #return JsonResponse({"error": f"Claim ID {claim_id} already exists in the database.Skip this"},status=400)
                                print(f"Claim ID {claim_id} already exists. Skipping creation.")
                                continue # Skip to the next claim if it exists
                            is_finalized = claim_status != "New"  # Set to False if claim_status is "New"

                            ClaimModel.objects.update_or_create(
                                patient_id=patient,
                                defaults={
                                    'claim_id': claim.get('claim_id'),
                                    'claim_status': claim.get('claim_status'),
                                    'disease_name': claim.get('disease_name'),
                                    'date_of_service': claim.get('date_of_service'),
                                    'treatment_given': claim.get('treatment_given'),
                                    'total_amount': claim.get('total_amount'),
                                    'lab_test': claim.get('lab_test'),
                                    'hospital_name': claim.get('hospital_name'),
                                    'hospital_address': claim.get('hospital_address'),
                                    'hospital_city': claim.get('hospital_city'),
                                    'hospital_state': claim.get('hospital_state'),
                                    'hospital_pincode': claim.get('hospital_pincode'),
                                    'last_timestamp': claim.get('last_timestamp'),
                                    'created_timestamp': claim.get('created_timestamp')                                }
                            )
                        except PatientModel.DoesNotExist:
                            return JsonResponse({"error": f"Patient with ID {patient_id} does not exist"}, status=404)
                    else:
                        return JsonResponse({"error": "Each claim should be a dictionary."}, status=400)
            else:
                return JsonResponse({"error": "Expected a list of claims."}, status=400)

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

        # Add a default return statement if everything goes well
        return JsonResponse({"success": "Claims processed successfully"}, status=200)

class ClaimApprovedView(generics.ListAPIView):
    serializer_class = ClaimSerializer
    SERVICE_ACCOUNT_FILE = os.path.join(settings.BASE_DIR, 'claim_app', 'service_account', 'service-account-file.json')
    SCOPES = ['https://www.googleapis.com/auth/drive.file']

    def get_queryset(self):
        # Get the start and end date from query parameters
        start_date = self.request.query_params.get('startdate')
        end_date = self.request.query_params.get('enddate')

        # Validate the input
        if not start_date or not end_date:
            return ClaimModel.objects.none()  # Return empty queryset if parameters are missing

        try:
            # Convert input strings to timezone-aware datetime objects
            start_datetime = timezone.datetime.fromisoformat(start_date)
            end_datetime = timezone.datetime.fromisoformat(end_date)
        except ValueError:
            return ClaimModel.objects.none()  # Return empty queryset if date format is invalid

        # Query the ClaimModel
        return ClaimModel.objects.filter(last_timestamp__range=(start_datetime, end_datetime)).filter(claim_status="Approved")


class ClaimExportView(ClaimApprovedView):
    def get(self, request, *args, **kwargs):
        logger.info("ClaimExportView GET method called with request: %s", request)
        queryset = self.get_queryset()

        if not queryset.exists():
            return Response({"error": "No claims found for the specified date range."}, status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(queryset, many=True)
        claims_data = serializer.data

        json_file_path = os.path.join(settings.BASE_DIR, 'claim_approved.json')
        try:
            with open(json_file_path, 'w') as json_file:
                json.dump(claims_data, json_file, indent=4)
            logger.info("JSON file created successfully at %s", json_file_path)
        except Exception as e:
            logger.error("Error writing JSON file: %s", str(e))
            return Response({"error": "Failed to create JSON file."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        if not os.path.exists(self.SERVICE_ACCOUNT_FILE):
            return Response({"error": "Service account file does not exist"}, status=status.HTTP_404_NOT_FOUND)

        try:
            credentials = service_account.Credentials.from_service_account_file(
                self.SERVICE_ACCOUNT_FILE, scopes=self.SCOPES
            )
            service = build('drive', 'v3', credentials=credentials)

            logger.info("Attempting to upload file to Google Drive.")

            file_metadata = {
                'name': 'claim_approved.json',
                'mimeType': 'application/json',
                'parents': ['root']  # Ensures the file goes to the root of My Drive

            }
            media = MediaFileUpload(json_file_path, mimetype='application/json')
            file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            
            logger.info("File uploaded successfully to Google Drive with file ID: %s", file.get('id'))

            # Share the file with your personal Google account
            file_id = file.get('id')  # The ID of the uploaded file
            email_to_share_with = 'your-email@example.com'  # Update this with your personal email

            permission = {
                'type': 'user',
                'role': 'writer',  # or 'reader' depending on your needs
                'emailAddress': "shanmugakala.p@kaditinnovations.com"
            }

            try:
                service.permissions().create(fileId=file_id, body=permission).execute()
                logger.info(f"File shared successfully with {shanmugakala.p@kaditinnovations.com}")
            except Exception as e:
                logger.error(f"An error occurred while sharing the file: {str(e)}")

            return Response({
                "success": "File exported and uploaded to Google Drive successfully.",
                "file_id": file.get('id')
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error("Error uploading file to Google Drive: %s", str(e))
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GoogleDriveExcelView(generics.GenericAPIView):
    SERVICE_ACCOUNT_FILE = os.path.join(settings.BASE_DIR, 'claim_app', 'service_account', 'service-account-file.json')
    SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

    def get(self, request):
        if not os.path.exists(self.SERVICE_ACCOUNT_FILE):
            return JsonResponse({"error": "Service account file does not exist"}, status=404)

        try:
            # Authenticate with the service account
            credentials = service_account.Credentials.from_service_account_file(
                self.SERVICE_ACCOUNT_FILE,
                scopes=self.SCOPES
            )
            service = build('drive', 'v3', credentials=credentials)

            # Search for `claim_new.json` in Google Drive
            results = service.files().list(q="name='2weeksplan_shanmugakala.xlsx'", fields="files(id)").execute()
            print(f"Items found:")  # Debug log
            return Response("File exist")
        
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)


