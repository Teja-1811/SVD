from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from datetime import datetime
from .models import Customer, CustomerMonthlyPurchase
from .customer_monthly_purchase_calculator import CustomerMonthlyPurchaseCalculator

def customer_monthly_purchases_dashboard(request):
    """
    Dashboard for viewing and managing customer monthly purchases
    """
    # Get filter parameters
    selected_month = request.GET.get('month', timezone.now().strftime('%Y-%m'))
    selected_customer = request.GET.get('customer', '')

    # Parse month and year
    try:
        year, month = map(int, selected_month.split('-'))
    except (ValueError, AttributeError):
        year = timezone.now().year
        month = timezone.now().month

    # Get all customers for dropdown
    customers = Customer.objects.all().order_by('name')

    # Get monthly purchase data
    if selected_customer:
        try:
            customer = Customer.objects.get(id=selected_customer)
            monthly_data = CustomerMonthlyPurchaseCalculator.get_customer_monthly_summary(
                customer, year-1, 1, year, month
            )
            customer_purchases = monthly_data
        except Customer.DoesNotExist:
            customer = None
            customer_purchases = []
            messages.error(request, 'Customer not found.')
    else:
        customer = None
        customer_purchases = []

    # Generate monthly report for the selected month
    monthly_report = CustomerMonthlyPurchaseCalculator.generate_monthly_purchase_report(
        year, month, include_zero_purchases=False
    )

    # Get top customers
    top_customers = CustomerMonthlyPurchaseCalculator.get_top_customers_by_purchase(
        year, month, limit=10
    )
    context = {
        'customers': customers,
        'selected_customer': selected_customer,
        'selected_customer_obj': customer,
        'selected_month': f"{year}-{month:02d}",
        'monthly_report': monthly_report,
        'customer_purchases': customer_purchases,
        'top_customers': top_customers,
        'current_year': year,
        'current_month': month,
    }

    return render(request, 'milk_agency/customer/monthly_purchases_dashboard.html', context)

def update_monthly_purchases(request):
    """
    View to manually trigger monthly purchase calculations
    """
    if request.method == 'POST':
        year = request.POST.get('year')
        month = request.POST.get('month')

        try:
            year = int(year) if year else timezone.now().year
            month = int(month) if month else timezone.now().month

            records_processed = CustomerMonthlyPurchaseCalculator.update_customer_monthly_purchase_records(year, month)

            messages.success(
                request,
                f'Successfully updated {records_processed} monthly purchase records for {month}/{year}'
            )

        except ValueError:
            messages.error(request, 'Invalid year or month provided.')
        except Exception as e:
            messages.error(request, f'Error updating monthly purchases: {str(e)}')

    return redirect('milk_agency:customer_monthly_purchases_dashboard')

def api_customer_monthly_purchases(request, customer_id):
    """
    API endpoint to get customer monthly purchase data
    """
    try:
        customer = Customer.objects.get(id=customer_id)

        # Get monthly purchases for the last 12 months
        now = timezone.now()
        monthly_data = CustomerMonthlyPurchaseCalculator.get_customer_monthly_summary(
            customer, now.year - 1, now.month, now.year, now.month
        )

        # Format data for JSON response
        data = {
            'customer': {
                'id': customer.id,
                'name': customer.name,
                'retailer_id': customer.retailer_id
            },
            'monthly_purchases': [
                {
                    'year': item['year'],
                    'month': item['month'],
                    'month_name': item['month_name'],
                    'purchase_volume': float(item['purchase_volume']),
                    'formatted_volume': f"₹{item['purchase_volume']:,.2f}"
                }
                for item in monthly_data
            ],
            'total_purchases': float(sum(item['purchase_volume'] for item in monthly_data)),
            'average_monthly': float(sum(item['purchase_volume'] for item in monthly_data) / len(monthly_data)) if monthly_data else 0
        }

        return JsonResponse(data)

    except Customer.DoesNotExist:
        return JsonResponse({'error': 'Customer not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def api_monthly_purchase_report(request, year, month):
    """
    API endpoint to get monthly purchase report
    """
    try:
        year = int(year)
        month = int(month)

        report = CustomerMonthlyPurchaseCalculator.generate_monthly_purchase_report(
            year, month, include_zero_purchases=False
        )

        # Format data for JSON response
        data = {
            'year': year,
            'month': month,
            'month_name': report['month_name'],
            'total_customers': report['total_customers'],
            'active_customers': report['active_customers'],
            'total_purchase_volume': float(report['total_purchase_volume']),
            'formatted_total': f"₹{report['total_purchase_volume']:,.2f}",
            'customers': [
                {
                    'id': customer_data['customer'].id,
                    'name': customer_data['customer'].name,
                    'retailer_id': customer_data['customer'].retailer_id,
                    'purchase_volume': float(customer_data['purchase_volume']),
                    'formatted_volume': f"₹{customer_data['purchase_volume']:,.2f}",
                    'has_purchases': customer_data['has_purchases']
                }
                for customer_data in report['customers']
            ]
        }

        return JsonResponse(data)

    except ValueError:
        return JsonResponse({'error': 'Invalid year or month'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
