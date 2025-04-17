from django.db import models
from django.db.models import JSONField

class Camera(models.Model):
    serial = models.CharField(max_length=50, unique=True)
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)

    def __str__(self):
        return self.serial

class Event(models.Model):
    camera = models.ForeignKey(Camera, on_delete=models.CASCADE)
    timestamp = models.DateTimeField()
    event_type = models.CharField(max_length=50)
    payload = JSONField()   
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"{self.camera.serial} - {self.event_type} at {self.timestamp}"
    
class User(models.Model):
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=100)
    reward = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.name} ({self.email}) - Reward: {self.reward}"