#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import yaml
import os
import hashlib
import uuid
from datetime import datetime, timezone, timedelta, UTC
from typing import Optional
from sqlmodel import SQLModel, Field, create_engine, Session, select
from locationsharinglib import Service
import argparse
from urllib.parse import quote
import requests

import threading
import time


class PersonModel(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: str = Field(default=None, primary_key=True)
    full_name: str
    nickname: Optional[str] = None
    latitude: float
    longitude: float
    timestamp: Optional[str] = None
    datetime: Optional[str] = None
    accuracy: Optional[float] = None
    address: Optional[str] = None
    country_code: Optional[str] = None
    charging: Optional[bool] = None
    battery_level: Optional[int] = None

    def __init__(self, **data):
        # Timestamp umwandeln, falls nötig
        raw_ts = data.get("datetime")
        if raw_ts is not None and not isinstance(raw_ts, str):
            try:
                data["datetime"] = datetime.fromtimestamp(float(raw_ts)/1000, tz=timezone.utc).isoformat()
            except (ValueError, TypeError):
                data["datetime"] = None  # fallback wenn ungültig

        super().__init__(**data)

        # ID aus Hash berechnen, falls nicht gesetzt
        if not self.id:
            self.id = self.compute_hash()

    def compute_hash(self) -> str:
        keys = [
            self.full_name, self.nickname, self.latitude, self.longitude,
            self.timestamp, self.accuracy, self.address, self.country_code,
            self.charging, self.battery_level
        ]
        values = [str(v) if v is not None else '' for v in keys]
        combined = "|".join(values)
        return hashlib.sha256(combined.encode('utf-8')).hexdigest()


class UploadedModel(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    
    id: str = Field(
        primary_key=True,
        foreign_key="personmodel.id"
    )
    upload_datetime: datetime = Field(default_factory=datetime.utcnow)
    
class ErrorMessageModel(SQLModel, table=True):
    __tablename__ = "errors"
    __table_args__ = {"extend_existing": True}

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)  # UUID als ID
    error_code: int = Field(..., description="Error Code")
    error_message: str = Field(default=None)  # Standardmäßig None, wird in der Validierung gesetzt
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    additional_info: Optional[str] = None

    def __init__(self, **data):
        super().__init__(**data)
        ERROR_CODES = {
            100: "Invalid cookie",
        }
        # Validierung des error_code und Setzen der error_message
        if self.error_code not in ERROR_CODES:
            raise ValidationError(f"Ungültiger Fehlercode: {self.error_code}")
        self.error_message = ERROR_CODES[self.error_code]

class LocationUpdater:
    def __init__(self, config_path: str = "./data/config.yml"):
        self.config = self.load_config(config_path)
        self.engine = self.setup_database(self.config)
        self.push = self._initialize_push()
        self.service = self._initialize_service()

    def _initialize_push(self):
        try:
            host = self.config['gotify']['host']
            token = self.config['gotify']['key']
            return PushNotify(host=host, token=token)
        except KeyError as e:
            raise ValueError(f"Missing configuration for PushNotify: {e}")

    def _initialize_service(self):
        try:
            return Service(
                cookies_file=os.path.abspath(self.config.get('cookies_path', './data/cookies.txt')),
                authenticating_account=self.config['email']
            )
        except Exception as e:
            if not self.error_codes_in_last(int(60*60*12)):
                self.add_error_code_to_db(100)
                self.push.send("Invalid cookie")
            raise ValueError("Invalid Cookies")

    def load_config(self, path: str):
        with open(path, 'r') as file:
            return yaml.safe_load(file)
        
    def add_error_code_to_db(self, error_code: int):
        """Fügt einen Fehlercode zur Datenbank hinzu."""
        with Session(self.engine) as session:
            error_entry = ErrorMessageModel(
                error_code=error_code
            )
            session.add(error_entry)
            session.commit()

    def error_codes_in_last(self, seconds: int) -> bool:
        """Überprüft, ob in der letzten Zeitspanne 'time' ein Fehlercode vorhanden war."""
        time_threshold = datetime.now(UTC) - timedelta(seconds=seconds)

        with Session(self.engine) as session:
            statement = select(ErrorMessageModel).where(ErrorMessageModel.timestamp >= time_threshold)
            results = session.exec(statement).all()

        return len(results) > 0 

    def setup_database(self, config):
        db_path = os.path.abspath(config.get('db_path', './data/data.db'))
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        database_url = f"sqlite:///{db_path}"
        engine = create_engine(database_url)
        SQLModel.metadata.create_all(engine, checkfirst=True)
        return engine

    def create_person(self, person_data):
        person = PersonModel(
            full_name=person_data['_full_name'],
            nickname=person_data['_nickname'],
            latitude=person_data['_latitude'],
            longitude=person_data['_longitude'],
            timestamp=person_data['_timestamp'],
            datetime=person_data['_timestamp'],
            accuracy=person_data['_accuracy'],
            address=person_data['_address'],
            country_code=person_data['_country_code'],
            charging=person_data['_charging'],
            battery_level=person_data['_battery_level']
        )

        with Session(self.engine) as session:
            existing = session.get(PersonModel, person.id)
            if existing:
                return existing
            session.add(person)
            session.commit()
            session.refresh(person)
            return person

    def create_uploaded(self, person: PersonModel):
        with Session(self.engine) as session:
            result = session.get(UploadedModel, person.id)
            if result:
                return result
            uploaded = UploadedModel(id=person.id)
            session.add(uploaded)
            session.commit()
            session.refresh(uploaded)
            return uploaded

    def update_database(self):
        for person_gpx in self.service.get_all_people():
            self.create_person(person_gpx.__dict__)

    def update_position(self, person: PersonModel) -> Optional[str]:
        phonetrack = self.config['phonetrack']
        session_name = quote(person.full_name)
        url = (
            f"https://{phonetrack['host']}/apps/phonetrack/logGet/{phonetrack['key']}/{session_name}?"
            f"lat={person.latitude}&lon={person.longitude}&alt=0&acc={person.accuracy or 0}"
            f"&bat={person.battery_level or 0}&sat=0&speed=0&bearing=0&timestamp={person.timestamp}"
        )

        try:
            response = requests.get(url)
            response.raise_for_status()
            self.create_uploaded(person)
            return response.text
        except requests.exceptions.RequestException as e:
            print(f"Fehler beim Senden der Anfrage: {e}")
            return None

    def ensure_all_positions_uploaded(self):
        with Session(self.engine) as session:
            all_persons = session.exec(select(PersonModel)).all()
            uploaded_ids = set(session.exec(select(UploadedModel.id)).all())
            not_uploaded = [p for p in all_persons if p.id not in uploaded_ids]

            results = []
            for person in not_uploaded:
                result = self.update_position(person)
                results.append((person.id, result))
            return results
        
    def run(self):
        self.update_database()
        self.ensure_all_positions_uploaded()
        
class CronJob(threading.Thread):
    def __init__(self, interval_seconds, target_function, *args, **kwargs):
        super().__init__()
        self.interval = interval_seconds
        self.target_function = target_function
        self.args = args
        self.kwargs = kwargs
        self._stop_event = threading.Event()

    def run(self):
        while not self._stop_event.is_set():
            start_time = time.time()
            try:
                self.target_function(*self.args, **self.kwargs)
            except Exception as e:
                print(f"Fehler beim Ausführen der Funktion: {e}")
            elapsed = time.time() - start_time
            time_to_wait = self.interval - elapsed
            if time_to_wait > 0:
                self._stop_event.wait(time_to_wait)

    def stop(self):
        self._stop_event.set()
        
class PushNotify:
    def __init__(self, host=None, token=None, **kwargs):
        if host is None or token is None:
            raise ValueError("Host and token must be provided.")

        if not host.startswith("https://"):
            host = "https://" + host
            
        self.host = host
        self.token = token
        self.payload = {
                            "priority": 8,
                            "title": 'GMAPS',
                        }
        self.payload.update(kwargs)
        
    def send(self, message):
        url = f"{self.host}/message?token={self.token}"
        payload = self.payload.copy()
        payload['message'] = message
        response = requests.post(url, json=payload)
        return response.status_code == 200

if __name__ == "__main__":
    pass
    self = LocationUpdater()

    
