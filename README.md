# SVD Agencies Management System

A comprehensive Django-based web application designed to manage operations for SVD Agencies, a milk distribution and general store business. The system provides tools for customer management, billing, inventory tracking, sales reporting, customer portal access, and order management.

## Features

### Core Modules

#### Milk Agency Management
- **Customer Management**: Custom user model with phone-based authentication, customer profiles including shop details, addresses, and financial tracking (due amounts, commission eligibility)
- **Product Inventory**: Item management with codes, names, companies, categories, pricing (buying/selling/MRP), stock quantities, piece counts, and image uploads
- **Billing System**: Automated bill generation with invoice numbers, itemized billing, discounts, profit calculations, and commission deductions
- **Sales Tracking**: Daily and monthly sales summaries, payment tracking, and retailer-wise reporting
- **Commission Management**: Monthly commission calculations based on milk/curd volumes, with deduction tracking
- **Financial Management**: Bank balance tracking, cashbook entries (denomination-wise), expenses, and daily/monthly payment summaries
- **PDF Reports**: Bill generation and monthly sales reports with PDF export

#### General Store Management
- **Product Management**: Products categorized by type, with buying/MRP pricing, stock tracking
- **Customer Management**: Customer records with contact details, addresses, and balance tracking
- **Sales System**: Invoice generation, itemized sales with discounts, profit calculations
- **Financial Tracking**: Bank balance, cashbook entries, investments, and expenses
- **Inventory Control**: Real-time stock updates and management

#### Customer Portal
- **Order Management**: Customer order placement with status tracking (pending, confirmed, processing, delivered, etc.), admin approval workflow
- **Order Items**: Detailed item requests with quantities, prices, discounts, and admin notes
- **Profile Management**: Customer profile updates and order history viewing
- **Bill Access**: View and download bills and statements

### Technical Features
- **Authentication**: Custom customer backend with phone-based login, staff/admin access
- **Responsive UI**: Bootstrap-styled web interface with real-time date/time display
- **PDF Generation**: ReportLab-based PDF creation for bills and reports
- **Data Export**: Excel export functionality for reports
- **Media Management**: Image uploads for products with organized storage
- **Real-time Dashboards**: Performance dashboards with analytics
- **API Integration**: Google API support for additional services
- **Database**: SQLite with comprehensive migrations for all models

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
│   ├── wsgi.py           # WSGI configuration
│   ├── asgi.py           # ASGI configuration
│   └── __pycache__/      # Python cache files
├── milk_agency/          # Milk agency app
│   ├── migrations/       # Database migrations
│   ├── static/           # App-specific static files
│   ├── templatetags/     # Custom template tags
│   └── views_*.py        # Various view modules
├── general_store/        # General store app
│   └── migrations/       # Database migrations
├── customer_portal/      # Customer portal app
│   └── migrations/       # Database migrations
├── templates/            # HTML templates
├── static/               # Static files (CSS, JS, images)
├── staticfiles/          # Collected static files for production
├── images/               # Uploaded media files
├── db.sqlite3           # SQLite database
├── manage.py            # Django management script
└── requirements.txt     # Python dependencies
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

## Recent Updates

### Version 1.0.3
- **General Store Model Updates**: Removed selling_price field from Product model and replaced all references with MRP
  - Updated views.py to use MRP instead of selling_price for pricing calculations
  - Updated admin.py to remove selling_price from list_display
  - Updated templates to remove selling_price fields and use MRP
  - Created and ran migration to remove selling_price field

### Version 1.0.2
- **UI Enhancements**: Added real-time time and date display to navigation bars
  - Updated customer_portal navbar with live time and date
  - Updated milk_agency navbar with live time and date
  - Enhanced base.js files for both modules with updateDateTime function

### Version 1.0.1
- **Production Deployment**: Configured Django for DuckDNS hosting
  - Updated ALLOWED_HOSTS in settings.py to include domain and IP
  - Added CSRF_TRUSTED_ORIGINS for the domain
  - Moved SECRET_KEY to environment variable for security
  - Ran collectstatic to prepare static files for production
  - Added production server setup instructions

## Version

Current version: 1.0.3
