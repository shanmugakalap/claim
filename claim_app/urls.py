from django.urls import path
from .views import LoginCreateView,LoginView,BulkCreate,PatientCreateView,ClaimCreateView,ClaimDetailsView,GoogleDriveView,ClaimApprovedView,ClaimExportView,GoogleDriveExcelView

urlpatterns = [
    path('logincreate/', LoginCreateView.as_view(), name ='login-create'),
    path('login/', LoginView.as_view(), name ='login-user'),
    path('patientcreate/', PatientCreateView.as_view(), name ='patient-create'),
    path('claimcreate/', ClaimCreateView.as_view(), name ='claim-create'),
    path('claim/<int:claim_id>/', ClaimDetailsView.as_view(), name='claim-detail'),
    path('googledriveview/', GoogleDriveView.as_view(), name = 'google-drive-json-dataupdate'),
    path('claimapproved/', ClaimApprovedView.as_view(), name = 'claim-approved-timesearch-details'),
    path('claimexportview/', ClaimExportView.as_view(), name = 'claim-approved-exportview'),
    path('googledriveexcelview/', GoogleDriveExcelView.as_view(), name = 'googledrive-exportview')
    
]