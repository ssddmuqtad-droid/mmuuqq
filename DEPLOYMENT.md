# 🚀 Deployment Guide

Complete guide for deploying the Dalal luxury real estate platform.

## 📋 Prerequisites

- Docker and Docker Compose installed
- Railway account (for production deployment)
- Domain name (optional)

## 🛠️ Local Development

### Using Docker Compose

```bash
# Clone the repository
git clone <repository-url>
cd acakar11

# Start all services
docker-compose up

# Access the applications
# Backend: http://localhost:8000
# Frontend: http://localhost:3000
```

### Manual Setup

#### Backend (Django)
```bash
cd acakar
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

#### Frontend (Next.js)
```bash
cd luxury-frontend
npm install
npm run dev
```

## ☁️ Railway Deployment

### Backend Deployment

The backend is already configured for Railway deployment:

1. **Backend Variables** (already set in Railway):
   ```
   PORT=8080
   DEBUG=False
   SECRET_KEY=your-secret-key
   DB_ENGINE=postgresql
   DATABASE_URL=railway-provided-url
   ```

2. **Build Command**:
   ```
   python manage.py collectstatic --noinput && gunicorn dalal_project.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120
   ```

### Frontend Deployment

1. **Create New Railway Service**:
   - Go to Railway dashboard
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Choose the repository
   - Set root directory to `luxury-frontend`

2. **Frontend Variables**:
   ```
   NEXT_PUBLIC_API_URL=https://your-backend-url.railway.app
   NODE_ENV=production
   ```

3. **Build Command**:
   ```
   npm run build
   ```

4. **Start Command**:
   ```
   npm start
   ```

### Railway Configuration Files

Create `luxury-frontend/railway.toml`:

```toml
[build]
builder = "NIXPACKS"

[deploy]
healthcheckPath = "/"
healthcheckTimeout = 300
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 10
```

## 🔧 Environment Variables

### Backend (.env)
```
DEBUG=False
SECRET_KEY=your-production-secret-key
DB_ENGINE=postgresql
DATABASE_URL=your-database-url
ALLOWED_HOSTS=yourdomain.com,.railway.app
```

### Frontend (.env.local)
```
NEXT_PUBLIC_API_URL=https://your-backend-url.railway.app
NODE_ENV=production
```

## 🌐 Custom Domain Setup

### Backend Domain
1. Go to Railway project settings
2. Add custom domain
3. Update DNS records
4. Update ALLOWED_HOSTS in Django settings

### Frontend Domain
1. Go to Railway frontend service
2. Add custom domain
3. Update DNS records

## 📊 Monitoring & Logs

### Railway Dashboard
- View logs in Railway dashboard
- Monitor resource usage
- Set up alerts for failures

### Health Checks
- Backend: `/api/health/`
- Frontend: `/`

## 🔒 Security Checklist

- [ ] Change default SECRET_KEY
- [ ] Enable HTTPS
- [ ] Set up CORS properly
- [ ] Configure security headers
- [ ] Enable rate limiting
- [ ] Set up database backups
- [ ] Review ALLOWED_HOSTS
- [ ] Enable DEBUG=False in production

## 📈 Performance Optimization

### Backend
- Enable database connection pooling
- Use Redis for caching
- Enable compression middleware
- Optimize database queries

### Frontend
- Enable image optimization
- Use CDN for static assets
- Enable compression
- Implement lazy loading

## 🔄 CI/CD Pipeline

### GitHub Actions Example

```yaml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Deploy to Railway
        uses: railwayapp/nixpacks-action@v1
        with:
          path: acakar

  deploy-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Deploy to Railway
        uses: railwayapp/nixpacks-action@v1
        with:
          path: luxury-frontend
```

## 🐛 Troubleshooting

### Common Issues

**Frontend can't connect to backend:**
- Check NEXT_PUBLIC_API_URL is correct
- Verify CORS settings in Django
- Ensure backend is accessible

**Django static files not loading:**
- Run `python manage.py collectstatic`
- Check STATIC_URL and STATIC_ROOT settings
- Verify Whitenoise middleware

**Build failures:**
- Check Node.js version compatibility
- Verify all dependencies are installed
- Review build logs in Railway

### Getting Help

- Check Railway documentation
- Review Docker logs
- Check Django logs
- Verify environment variables

## 📝 Post-Deployment Checklist

- [ ] Test all API endpoints
- [ ] Verify frontend-backend communication
- [ ] Test user authentication
- [ ] Verify file uploads work
- [ ] Test email notifications
- [ ] Check responsive design
- [ ] Verify SEO metadata
- [ ] Test performance
- [ ] Set up monitoring
- [ ] Configure backups

## 🎯 Success Metrics

Monitor these metrics after deployment:

- Page load time < 3 seconds
- API response time < 500ms
- Error rate < 1%
- Uptime > 99.9%
- Mobile responsiveness 100%

---

**Deployment complete! 🎉**