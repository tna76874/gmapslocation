#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import yaml
from locationsharinglib import Service
from sqlmodel import SQLModel, Field, create_engine, Session
from typing import Optional
import uuid
import hashlib
from datetime import datetime, timezone
import os

class PersonModel(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: str = Field(default=None, primary_key=True)
    full_name: str
    nickname: Optional[str] = None
    latitude: float
    longitude: float
    timestamp: Optional[str] = None
    accuracy: Optional[float] = None
    address: Optional[str] = None
    country_code: Optional[str] = None
    charging: Optional[bool] = None
    battery_level: Optional[int] = None

    def __init__(self, **data):
        # Timestamp umwandeln, falls nötig
        raw_ts = data.get("timestamp")
        if raw_ts is not None and not isinstance(raw_ts, str):
            try:
                data["timestamp"] = datetime.fromtimestamp(float(raw_ts)/1000, tz=timezone.utc).isoformat()
            except (ValueError, TypeError):
                data["timestamp"] = None  # fallback wenn ungültig

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



# Lade die Konfiguration aus der config.yml
with open('./data/config.yml', 'r') as file:
    config = yaml.safe_load(file)
    
# SQLite-Datenbank erstellen oder verbinden
DATABASE_PATH = os.path.abspath(config.get('db_path', './data/data.db'))

# Verzeichnis für die Datenbankdatei sicherstellen
db_directory = os.path.dirname(DATABASE_PATH)

if not os.path.exists(db_directory):
    os.makedirs(db_directory)

DATABASE_URL = f"sqlite:///{DATABASE_PATH}"
engine = create_engine(DATABASE_URL)

# Tabellen erstellen
SQLModel.metadata.create_all(engine, checkfirst=True)

# Beispiel zur Verwendung des Modells und zum Speichern in der Datenbank
def create_person(person_data):
    person = PersonModel(
        full_name=person_data['_full_name'],
        nickname=person_data['_nickname'],
        latitude=person_data['_latitude'],
        longitude=person_data['_longitude'],
        timestamp=person_data['_timestamp'],
        accuracy=person_data['_accuracy'],
        address=person_data['_address'],
        country_code=person_data['_country_code'],
        charging=person_data['_charging'],
        battery_level=person_data['_battery_level']
    )
    
    with Session(engine) as session:
        # Prüfe, ob die ID bereits existiert
        existing = session.get(PersonModel, person.id)
        if existing:
            return None

        session.add(person)
        session.commit()
        session.refresh(person)
        return person

cookies_file = os.path.abspath(config.get('cookies_path', './data/cookies.txt'))
google_email = config['email']

service = Service(cookies_file=cookies_file, authenticating_account=google_email)

for person_gpx in service.get_all_people():
    print(person_gpx)
    create_person(person_gpx.__dict__)
