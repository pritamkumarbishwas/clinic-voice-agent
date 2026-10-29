import os

os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017")
os.environ.setdefault("MONGODB_DATABASE", "clinic_voice_ai_test")
os.environ.setdefault(
    "JWT_SECRET",
    "test-only-secret-that-is-long-enough-for-hs256",
)




