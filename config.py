import os

class Config:
    # Güvenlik için rastgele bir anahtar
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'TorontoCarRental_Secret_Key_2026'
    
    # Sizin veritabanı bağlantı adresiniz (İlk mesajınızdan alınmıştır)
    # Hata almamak için zaman aşımı sürelerini (Timeout) artırdık.
    MONGODB_SETTINGS = {
        'host': 'mongodb+srv://Torontocarental:inan.1907@cluster0.oht1igm.mongodb.net/CarRentalDB?retryWrites=true&w=majority',
        'connectTimeoutMS': 30000,
        'socketTimeoutMS': 30000
    }

    # API Anahtarları (Buralara kendi anahtarlarınızı yazacaksınız)
    # Şu an test için "sandbox" değerleri girili.
    SQUARE_ACCESS_TOKEN = "EAAA_SQUARE_SANDBOX_TOKEN_HERE"
    SQUARE_LOCATION_ID = "SQUARE_LOCATION_ID_HERE"
    
    # WhatsApp numaranız (Başında + olmadan ülke kodu ile)
    WHATSAPP_NUMBER = "1555019988" 
    
    # Google Maps API Anahtarı (Harita için)
    GOOGLE_MAPS_API_KEY = "AIzaSy_YOUR_GOOGLE_MAPS_KEY"
    
    # Kanada Doları -> ABD Doları dönüşüm oranı
    CAD_TO_USD = 0.74