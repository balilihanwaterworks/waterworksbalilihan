import os

dashboard_views = r'd:\balilihan_waterworks\waterworks\consumers\views\dashboard_views.py'
cashier_income = r'd:\balilihan_waterworks\waterworks\consumers\templates\consumers\cashier_income.html'
print_remit_tmpl = r'd:\balilihan_waterworks\waterworks\consumers\templates\consumers\print_cashier_remittance.html'

# -------------------------------------------------------------
# 1. Update dashboard_views.py
# -------------------------------------------------------------
with open(dashboard_views, 'r', encoding='utf-8') as f:
    views_code = f.read()

print_totals_old = """    # Retrieve totals for this user
    today_total = Payment.objects.filter(
        processed_by=target_user,
        payment_date__date=today
    ).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')

    month_total = Payment.objects.filter(
        processed_by=target_user,
        payment_date__month=current_month,
        payment_date__year=current_year
    ).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')

    period_total = Payment.objects.filter(
        processed_by=target_user,
        payment_date__date__gte=filter_start,
        payment_date__date__lte=filter_end
    ).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
    
    period_count = Payment.objects.filter(
        processed_by=target_user,
        payment_date__date__gte=filter_start,
        payment_date__date__lte=filter_end
    ).count()

    alltime_total = Payment.objects.filter(
        processed_by=target_user
    ).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')

    # Get consumers processed
    consumers_list = []
    from django.db.models import Count
    my_payments = Payment.objects.filter(
        payment_date__date__gte=filter_start,
        payment_date__date__lte=filter_end,
        processed_by=target_user
    )"""

print_totals_new = """    barangay_filter = request.GET.get('barangay', '')
    
    base_qs = Payment.objects.filter(processed_by=target_user)
    if barangay_filter:
        base_qs = base_qs.filter(bill__consumer__barangay_id=barangay_filter)

    # Retrieve totals for this user
    today_total = base_qs.filter(
        payment_date__date=today
    ).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')

    month_total = base_qs.filter(
        payment_date__month=current_month,
        payment_date__year=current_year
    ).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')

    period_total = base_qs.filter(
        payment_date__date__gte=filter_start,
        payment_date__date__lte=filter_end
    ).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
    
    period_count = base_qs.filter(
        payment_date__date__gte=filter_start,
        payment_date__date__lte=filter_end
    ).count()

    alltime_total = base_qs.aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')

    # Get consumers processed
    consumers_list = []
    from django.db.models import Count
    my_payments = base_qs.filter(
        payment_date__date__gte=filter_start,
        payment_date__date__lte=filter_end
    )"""
views_code = views_code.replace(print_totals_old, print_totals_new)

# Make sure we pass the barangay name to the context
ctx_old = "'consumers_list': consumers_list,"
ctx_new = """'consumers_list': consumers_list,
        'selected_barangay_name': Barangay.objects.get(id=barangay_filter).name if barangay_filter else 'All Barangays',"""
views_code = views_code.replace(ctx_old, ctx_new)

with open(dashboard_views, 'w', encoding='utf-8') as f:
    f.write(views_code)


# -------------------------------------------------------------
# 2. Update cashier_income.html (Back button & Modal UI)
# -------------------------------------------------------------
with open(cashier_income, 'r', encoding='utf-8') as f:
    tmpl = f.read()

# Replace Back button
back_btn_old = """            <div class="flex items-center gap-2">
                <a href="{% url 'consumers:home' %}" class="px-4 py-2 bg-white border border-light-300 text-dark-700 text-sm font-medium rounded-lg hover:bg-light-50 transition-colors flex items-center gap-2">
                    <i class="bi bi-arrow-left"></i>
                    Back to Dashboard
                </a>
            </div>"""
back_btn_new = """            <div class="flex items-center gap-2">
                <a href="{% url 'consumers:home' %}" class="text-dark-500 hover:text-dark-800 text-sm font-medium transition-colors flex items-center gap-1.5">
                    <i class="bi bi-arrow-left"></i>
                    Back
                </a>
            </div>"""
tmpl = tmpl.replace(back_btn_old, back_btn_new)

# Replace Print Button Action
print_btn_old = """                <div class="px-4 pb-3 flex gap-2">
                    <a href="{% url 'consumers:print_cashier_remittance' cashier.user_id %}?filter={{ filter_type }}&month_from={{ month_from }}&year_from={{ year_from }}&month_to={{ month_to }}&year_to={{ year_to }}"
                       target="_blank"
                       class="w-full flex items-center justify-center gap-1.5 px-2 py-2 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 text-emerald-700 hover:text-emerald-800 text-[12px] font-bold rounded-lg transition-colors">
                        <i class="bi bi-printer-fill text-emerald-600"></i>
                        Print Summary
                    </a>
                </div>"""
print_btn_new = """                <div class="px-4 pb-3 flex gap-2">
                    <button type="button" onclick="openPrintModal('{% url 'consumers:print_cashier_remittance' cashier.user_id %}?filter={{ filter_type }}&month_from={{ month_from }}&year_from={{ year_from }}&month_to={{ month_to }}&year_to={{ year_to }}')"
                       class="w-full flex items-center justify-center gap-1.5 px-2 py-2 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 text-emerald-700 hover:text-emerald-800 text-[12px] font-bold rounded-lg transition-colors">
                        <i class="bi bi-printer-fill text-emerald-600"></i>
                        Print Summary
                    </button>
                </div>"""
tmpl = tmpl.replace(print_btn_old, print_btn_new)

# Inject Modal Structure at the end before {% endblock %}
modal_html = """
    <!-- Print Filter Modal -->
    <div id="printModal" class="hidden fixed inset-0 z-[100] bg-dark-900/60 backdrop-blur-sm flex items-center justify-center p-4">
        <div class="bg-white rounded-xl shadow-2xl w-full max-w-sm overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            <div class="flex items-center justify-between p-4 border-b border-light-200">
                <h3 class="font-bold text-dark-800 flex items-center gap-2">
                    <i class="bi bi-printer text-emerald-600"></i>
                    Print Options
                </h3>
                <button type="button" onclick="closePrintModal()" class="text-dark-400 hover:text-dark-700 transition-colors">
                    <i class="bi bi-x-lg"></i>
                </button>
            </div>
            <div class="p-5">
                <label class="block text-sm text-dark-700 font-medium mb-2">Filter by Barangay</label>
                <select id="modal_barangay" class="w-full px-4 py-2 border border-light-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500 mb-5">
                    <option value="">-- All Barangays --</option>
                    {% for brgy in all_barangays %}
                        <option value="{{ brgy.id }}">{{ brgy.name }}</option>
                    {% endfor %}
                </select>
                
                <div class="flex gap-2 justify-end">
                    <button type="button" onclick="closePrintModal()" class="px-4 py-2 bg-white border border-light-300 text-dark-700 hover:bg-light-50 rounded-lg text-sm font-semibold transition-colors">
                        Cancel
                    </button>
                    <button type="button" onclick="confirmPrint()" class="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white shadow-sm rounded-lg text-sm font-bold transition-colors flex items-center gap-1.5">
                        <i class="bi bi-printer-fill"></i>
                        Proceed to Print
                    </button>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        let currentPrintUrl = '';

        function openPrintModal(baseUrl) {
            currentPrintUrl = baseUrl;
            document.getElementById('printModal').classList.remove('hidden');
        }

        function closePrintModal() {
            document.getElementById('printModal').classList.add('hidden');
            document.getElementById('modal_barangay').value = '';
            currentPrintUrl = '';
        }

        function confirmPrint() {
            const barangayId = document.getElementById('modal_barangay').value;
            let finalUrl = currentPrintUrl;
            if (barangayId) {
                finalUrl += '&barangay=' + encodeURIComponent(barangayId);
            }
            window.open(finalUrl, '_blank');
            closePrintModal();
        }
    </script>
"""
if "<!-- Print Filter Modal -->" not in tmpl:
    tmpl = tmpl.replace("{% endblock %}", modal_html + "\n{% endblock %}")

with open(cashier_income, 'w', encoding='utf-8') as f:
    f.write(tmpl)

# -------------------------------------------------------------
# 3. Update print_cashier_remittance.html header
# -------------------------------------------------------------
with open(print_remit_tmpl, 'r', encoding='utf-8') as f:
    ptmpl = f.read()

sub_title_old = "<h2>Individual Cashier Remittance Summary</h2>"
sub_title_new = "<h2>Individual Cashier Remittance Summary<br><small style='font-size: 11px; color: #666;'>[{{ selected_barangay_name }}]</small></h2>"
ptmpl = ptmpl.replace(sub_title_old, sub_title_new)

with open(print_remit_tmpl, 'w', encoding='utf-8') as f:
    f.write(ptmpl)

print("Updates to layout and print logic applied.")
