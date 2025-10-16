# inventory/views.py
from django.views.generic import ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q

from .models import Inventory, StockMovement, StockAlert
from products.models import Product


class StaffRequiredMixin(LoginRequiredMixin):
    """Mixin to require staff status."""
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_staff:
            messages.error(request, "You don't have permission to access inventory.")
            return redirect('home')  # Or login redirect
        return super().dispatch(request, *args, **kwargs)


class InventoryDashboard(StaffRequiredMixin, ListView):
    """Dashboard overview."""
    model = Inventory
    template_name = 'inventory/dashboard.html'
    context_object_name = 'inventories'
    paginate_by = 10

    def get_queryset(self):
        return Inventory.objects.select_related('product').all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['low_stock_count'] = Inventory.objects.low_stock().count()
        context['out_of_stock_count'] = Inventory.objects.out_of_stock().count()
        context['recent_movements'] = StockMovement.objects.select_related('inventory__product').order_by('-created_at')[:5]
        context['active_alerts'] = StockAlert.objects.filter(status='active').count()
        return context


class InventoryListView(StaffRequiredMixin, ListView):
    """List all inventory with search/filter."""
    model = Inventory
    template_name = 'inventory/list.html'
    context_object_name = 'inventories'
    paginate_by = 20

    def get_queryset(self):
        queryset = Inventory.objects.select_related('product').all()
        query = self.request.GET.get('q')
        location = self.request.GET.get('location')
        if query:
            queryset = queryset.filter(Q(product__products_name__icontains=query) | Q(batch_number__icontains=query))
        if location:
            queryset = queryset.filter(location=location)
        return queryset.order_by('-last_updated')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['locations'] = Inventory.objects.values_list('location', flat=True).distinct()
        return context


class InventoryDetailView(StaffRequiredMixin, DetailView):
    """Detail view with movements and alerts."""
    model = Inventory
    template_name = 'inventory/detail.html'
    context_object_name = 'inventory'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['movements'] = self.object.movements.select_related('created_by').order_by('-created_at')[:10]
        context['alerts'] = self.object.alerts.order_by('-created_at')
        return context

    def post(self, request, *args, **kwargs):
        # Handle quick reserve/consume (extend as needed)
        action = request.POST.get('action')
        quantity = int(request.POST.get('quantity', 0))
        inventory = self.get_object()
        if action == 'reserve' and quantity > 0:
            if inventory.reserve_stock(quantity, reference="Manual Reserve"):
                messages.success(request, f"Reserved {quantity} units.")
            else:
                messages.error(request, "Not enough stock to reserve.")
        return redirect('inventory:detail', pk=inventory.pk)


def restock_inventory(request, pk):
    """Restock via form (uses model's add_stock)."""
    inventory = get_object_or_404(Inventory, pk=pk)
    if not request.user.is_staff:
        messages.error(request, "Permission denied.")
        return redirect('inventory:list')

    if request.method == 'POST':
        quantity = int(request.POST.get('quantity', 0))
        note = request.POST.get('note', '')
        if quantity > 0:
            inventory.add_stock(quantity, created_by=request.user, reference="Manual Restock")
            messages.success(request, f"Added {quantity} units to stock.")
        else:
            messages.error(request, "Invalid quantity.")
        return redirect('inventory:detail', pk=pk)

    return render(request, 'inventory/restock_form.html', {'inventory': inventory})


def add_movement(request, inventory_id):
    """Add custom stock movement (AJAX or POST)."""
    inventory = get_object_or_404(Inventory, pk=inventory_id)
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'message': 'Permission denied.'})

    if request.method == 'POST':
        movement_type = request.POST.get('movement_type')
        quantity = int(request.POST.get('quantity', 0))
        reference = request.POST.get('reference', '')
        note = request.POST.get('note', '')

        if movement_type in ['in', 'return']:
            qty = abs(quantity)
        elif movement_type in ['out', 'damaged']:
            qty = -abs(quantity)
        else:
            return JsonResponse({'success': False, 'message': 'Invalid type.'})

        movement = StockMovement.objects.create(
            inventory=inventory,
            movement_type=movement_type,
            quantity=qty,
            reference=reference,
            note=note,
            created_by=request.user
        )
        return JsonResponse({'success': True, 'message': 'Movement logged.'})

    return JsonResponse({'success': False, 'message': 'Invalid method.'})


class StockAlertListView(StaffRequiredMixin, ListView):
    """List and manage alerts."""
    model = StockAlert
    template_name = 'inventory/alerts.html'
    context_object_name = 'alerts'
    paginate_by = 15

    def get_queryset(self):
        return StockAlert.objects.select_related('inventory__product', 'resolved_by').filter(status='active').order_by('-created_at')

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')
        alert_ids = request.POST.getlist('alert_ids')
        alerts = StockAlert.objects.filter(id__in=alert_ids)
        if action == 'resolve':
            for alert in alerts:
                alert.resolve(user=request.user)
            messages.success(request, f"{alerts.count()} alert(s) resolved.")
        elif action == 'dismiss':
            alerts.update(status='dismissed')
            messages.success(request, f"{alerts.count()} alert(s) dismissed.")
        return redirect('inventory:alerts')