from django.urls import path
from .views import register_user, monitor_page, request_reward, readjust

urlpatterns = [
    path('register/', register_user, name='register_user'),
    path('monitor/', monitor_page, name='monitor_page'),
    path('reward/', request_reward, name='compare_detection'),
    path('readjust/', readjust, name='readjust')
]