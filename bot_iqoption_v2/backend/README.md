# IQ Option Trading Bot - Backend

Modern Django-based backend for IQ Option trading bot with REST API, WebSocket support, and real-time monitoring.

## Features

- **User Authentication**: JWT-based authentication with encrypted IQ Option credentials
- **Trading Strategies**: MHI, Torres Gêmeas, and MHI M5 strategies migrated from legacy system
- **Real-time Monitoring**: WebSocket connections for live trading updates
- **Asset Cataloging**: Automated analysis of asset performance across strategies
- **Martingale & Soros**: Advanced money management systems
- **Background Tasks**: Celery integration for async trading operations
- **Comprehensive Logging**: Detailed logging and audit trails

## Architecture

```
backend/
├── bot_iqoption/          # Django project settings
├── accounts/              # User management and authentication
├── trading/               # Core trading functionality
│   ├── models.py         # Database models
│   ├── views.py          # API endpoints
│   ├── serializers.py    # Data serialization
│   ├── iq_api.py         # IQ Option API wrapper
│   ├── strategies.py     # Trading strategies
│   ├── catalog.py        # Asset cataloging service
│   ├── consumers.py      # WebSocket consumers
│   └── routing.py        # WebSocket routing
├── requirements.txt       # Python dependencies
├── celery_app.py         # Celery configuration
└── manage.py             # Django management
```

## Installation

1. **Clone and setup environment**:
```bash
cd bot_iqoption_v2/backend
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

2. **Install IQ Option API**:
```bash
pip install git+https://github.com/Lu-Yi-Hsun/iqoptionapi.git
```

3. **Setup environment variables**:
```bash
copy .env.example .env
# Edit .env with your configuration
```

4. **Setup database**:
```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
```

5. **Start services**:
```bash
# Terminal 1: Django server
python manage.py runserver

# Terminal 2: Celery worker
celery -A bot_iqoption worker -l info

# Terminal 3: Redis server (required for Celery and WebSockets)
redis-server
```

## API Endpoints

### Authentication
- `POST /api/auth/register/` - User registration
- `POST /api/auth/login/` - User login
- `POST /api/auth/logout/` - User logout
- `GET /api/auth/profile/` - Get user profile
- `PUT /api/auth/profile/` - Update user profile

### IQ Option Integration
- `POST /api/auth/iq-credentials/` - Set IQ Option credentials
- `GET /api/auth/iq-credentials/` - Get IQ Option credentials status
- `POST /api/trading/connection/test/` - Test IQ Option connection
- `GET /api/trading/connection/status/` - Get connection status

### Trading Configuration
- `GET /api/auth/trading-config/` - Get trading configuration
- `PUT /api/auth/trading-config/` - Update trading configuration

### Trading Operations
- `POST /api/trading/start/` - Start trading session
- `POST /api/trading/stop/` - Stop trading session
- `GET /api/trading/sessions/` - List trading sessions
- `GET /api/trading/sessions/active/` - Get active session
- `GET /api/trading/operations/` - List trading operations

### Asset Cataloging
- `POST /api/trading/catalog/` - Start asset cataloging
- `GET /api/trading/catalog/results/` - Get catalog results

### Monitoring
- `GET /api/trading/dashboard/` - Get dashboard data
- `GET /api/trading/logs/` - Get trading logs
- `GET /api/auth/dashboard/` - Get user dashboard data

### WebSocket Endpoints
- `ws://localhost:8000/ws/trading/` - Real-time trading updates
- `ws://localhost:8000/ws/monitoring/` - Market monitoring updates

## Models

### User Model
Extended Django user with encrypted IQ Option credentials and trading preferences.

### Trading Models
- **TradingSession**: Individual trading sessions with strategy and results
- **Operation**: Individual trading operations with entry/exit data
- **AssetCatalog**: Asset performance analysis results
- **TradingLog**: Comprehensive logging system
- **MarketData**: Historical market data storage

## Trading Strategies

### MHI (3 Candles)
Analyzes the last 3 candles to determine entry direction based on color patterns.

### Torres Gêmeas (1 Candle)
Uses the 4th candle back to determine entry direction, focusing on specific entry times.

### MHI M5 (5-minute timeframe)
Similar to MHI but operates on 5-minute candles for longer-term analysis.

## Security Features

- **Encrypted Credentials**: IQ Option credentials encrypted per user
- **JWT Authentication**: Secure token-based authentication
- **CORS Protection**: Configured for frontend integration
- **Input Validation**: Comprehensive data validation
- **Audit Logging**: Complete audit trail of all operations

## Configuration

Key settings in `.env`:

```env
SECRET_KEY=your-django-secret-key
DATABASE_URL=postgresql://user:pass@localhost/db
REDIS_URL=redis://localhost:6379/0
JWT_SECRET_KEY=your-jwt-secret
CORS_ALLOWED_ORIGINS=http://localhost:3000
```

## Development

### Running Tests
```bash
python manage.py test
```

### Code Formatting
```bash
black .
flake8 .
```

### Database Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

### Admin Interface
Access Django admin at `http://localhost:8000/admin/` to manage users, sessions, and view logs.

## Production Deployment

1. Set `DEBUG=False` in environment
2. Configure proper database (PostgreSQL recommended)
3. Setup Redis for production
4. Use Gunicorn for WSGI server
5. Configure reverse proxy (Nginx)
6. Setup SSL certificates
7. Configure Celery with supervisor

## Troubleshooting

### Common Issues

1. **IQ Option Connection Failed**
   - Verify credentials are correct
   - Check if account is not blocked
   - Ensure stable internet connection

2. **WebSocket Connection Issues**
   - Verify Redis is running
   - Check CORS settings
   - Ensure proper authentication

3. **Celery Tasks Not Running**
   - Start Celery worker
   - Check Redis connection
   - Verify task registration

### Logs

Check logs in:
- Django: Console output or configured log file
- Celery: Worker console output
- Trading: Database `TradingLog` model

## Support

For issues and questions:
1. Check the logs for detailed error messages
2. Verify all services are running (Django, Redis, Celery)
3. Ensure IQ Option credentials are valid
4. Check network connectivity
