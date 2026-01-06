from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db import transaction
from decimal import Decimal
from milk_agency.models import Bill, BillItem, Customer, Item
from milk_agency.serializers import BillSerializer, BillItemSerializer

# filepath: c:\Users\bhanu\OneDrive\Desktop\SVD\api\admin_bills.py


class BillViewSet(viewsets.ModelViewSet):
    """
    API ViewSet for managing bills.
    Provides CRUD operations and custom actions for bill management.
    """
    queryset = Bill.objects.select_related('customer').prefetch_related('billitem_set')
    serializer_class = BillSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        customer_id = self.request.query_params.get('customer', None)
        start_date = self.request.query_params.get('start_date', None)
        end_date = self.request.query_params.get('end_date', None)

        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)
        if start_date:
            queryset = queryset.filter(invoice_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(invoice_date__lte=end_date)

        return queryset.order_by('-invoice_date')

    @action(detail=False, methods=['get'])
    def anonymous_bills(self, request):
        """Get all bills without customers."""
        bills = Bill.objects.filter(customer__isnull=True).order_by('-invoice_date')
        serializer = self.get_serializer(bills, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['delete'])
    def delete_bill(self, request, pk=None):
        """Delete a bill and revert stock & customer due."""
        bill = self.get_object()
        bill_items = BillItem.objects.filter(bill=bill)

        try:
            with transaction.atomic():
                # Revert stock
                for bill_item in bill_items:
                    bill_item.item.stock_quantity += bill_item.quantity
                    bill_item.item.save()

                # Revert customer due
                if bill.customer:
                    bill.customer.due -= bill.total_amount
                    bill.customer.save()

                # Delete bill items and bill
                bill_items.delete()
                bill.delete()

            return Response(
                {'message': 'Bill deleted successfully. Stock and customer due updated.'},
                status=status.HTTP_204_NO_CONTENT
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['get'])
    def bill_details(self, request, pk=None):
        """Get bill with all items and calculations."""
        bill = self.get_object()
        bill_items = BillItem.objects.filter(bill=bill).select_related('item')
        current_due = bill.op_due_amount + bill.total_amount

        data = {
            'bill': BillSerializer(bill).data,
            'items': BillItemSerializer(bill_items, many=True).data,
            'current_due': float(current_due)
        }
        return Response(data)