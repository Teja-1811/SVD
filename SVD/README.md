# SVD Agencies Management System

A comprehensive Django-based web application designed to manage operations for SVD Agencies, a milk distribution and general store business. The system provides tools for customer management, billing, inventory tracking, sales reporting, and customer portal access.

## Features

### Core Modules
- **Milk Agency Management**: Complete milk product inventory, customer billing, and delivery tracking
- **General Store**: Product management, sales tracking, and customer records
- **Customer Portal**: Online ordering, bill viewing, and profile management
- **Bill Generation**: Automated bill creation with PDF export capabilities
- **Bills Dashboard**: View and manage all bills with customer filtering
- **Sales Analytics**: Monthly sales summaries, category-wise reporting, and performance dashboards
- **Stock Management**: Real-time inventory tracking and stock updates
- **Cashbook & Payments**: Financial transaction recording and payment tracking
- **PDF Reports**: Generate detailed bills and monthly sales reports

### Technical Features
- User authentication with custom customer backend
- Responsive web interface with Bootstrap styling
- PDF generation using ReportLab
- Excel export functionality
- Google API integration for additional services
- Image upload and management for products
- Real-time data dashboards

## Installation

### Prerequisites
- Python 3.8 or higher
- Virtual environment (recommended)

### Setup Steps

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd SVD
   ```

2. **Create and activate virtual environment**
   ```bash
   python -m venv venv
   venv\Scripts\activate  # On Windows
   # source venv/bin/activate  # On Linux/Mac
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Database setup**
   ```bash
   python manage.py migrate
   ```

5. **Create superuser (optional)**
   ```bash
   python manage.py createsuperuser
   ```

6. **Run the development server**
   ```bash
   python manage.py runserver
   ```

7. **Access the application**
   - Open your browser and go to `http://127.0.0.1:8000/`

## Usage

### For Administrators
- Access admin panel at `/admin/` for system configuration
- Manage products, customers, and inventory through dedicated dashboards
- Generate reports and export data

### For Customers
- Register/Login through the customer portal
- Place orders and view order history
- Download bills and statements
- Update profile information

### Key URLs
- `/` - Home dashboard
- `/admin/` - Django admin panel
- `/customer/login/` - Customer login
- `/milk-agency/` - Milk agency management
- `/general-store/` - General store management

## Project Structure

```
SVD/
├── SVD/                    # Main Django project
│   ├── settings.py        # Project settings
│   ├── urls.py           # Main URL configuration
│   └── wsgi.py           # WSGI configuration
├── milk_agency/          # Milk agency app
├── general_store/        # General store app
├── customer_portal/      # Customer portal app
├── templates/            # HTML templates
├── static/               # Static files (CSS, JS, images)
├── images/               # Uploaded media files
└── db.sqlite3           # SQLite database
```

## Dependencies

The application uses the following key packages:
- Django 5.2.6 - Web framework
- django-mathfilters - Mathematical operations in templates
- reportlab - PDF generation
- num2words - Number to words conversion
- Pillow - Image processing
- xlwt - Excel file creation
- google-api-python-client - Google API integration

See `requirements.txt` for complete list.

## Configuration

### Settings
Key settings in `SVD/settings.py`:
- `DEBUG = True` (set to False in production)
- `ALLOWED_HOSTS = []` (add your domain in production)
- Custom user model: `milk_agency.Customer`
- Media files served from `/media/` URL

### Static Files
- Static files are collected in `staticfiles/` directory
- Served via `/static/` URL in production

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-feature`)
3. Commit your changes (`git commit -am 'Add new feature'`)
4. Push to the branch (`git push origin feature/new-feature`)
5. Create a Pull Request

## License

This project is proprietary software for SVD Agencies.

## Support

For technical support or questions, please contact the development team.

## Version

Current version: 1.0.0
