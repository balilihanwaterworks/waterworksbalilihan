import os
import re

dashboard_views = r'd:\balilihan_waterworks\waterworks\consumers\views\dashboard_views.py'
cashier_income = r'd:\balilihan_waterworks\waterworks\consumers\templates\consumers\cashier_income.html'
print_remit_tmpl = r'd:\balilihan_waterworks\waterworks\consumers\templates\consumers\print_cashier_remittance.html'

# 1. Update dashboard_views.py
with open(dashboard_views, 'r', encoding='utf-8') as f:
    views_code = f.read()

date_logic_original = """    # --- Date filter from GET params ---
    date_from_str = request.GET.get('date_from', '')
    date_to_str = request.GET.get('date_to', '')
    filter_type = request.GET.get('filter', 'month')  # 'today', 'month', 'custom'

    if filter_type == 'today':
        filter_start = today
        filter_end = today
        selected_month = current_month
        selected_year = current_year
    elif filter_type == 'custom' and date_from_str and date_to_str:
        try:
            filter_start = datetime.strptime(date_from_str, '%Y-%m-%d').date()
            filter_end = datetime.strptime(date_to_str, '%Y-%m-%d').date()
        except ValueError:
            filter_start = date(current_year, current_month, 1)
            filter_end = today
        selected_month = current_month
        selected_year = current_year
    else:
        # Default is month filter
        filter_type = 'month'
        month_param = request.GET.get('month')
        year_param = request.GET.get('year')
        if month_param and year_param:
            try:
                selected_month = int(month_param)
                selected_year = int(year_param)
            except ValueError:
                selected_month = current_month
                selected_year = current_year
        else:
            selected_month = current_month
            selected_year = current_year

        import calendar
        _, last_day = calendar.monthrange(selected_year, selected_month)
        filter_start = date(selected_year, selected_month, 1)
        filter_end = date(selected_year, selected_month, last_day)"""

date_logic_new = """    # --- Date filter from GET params ---
    filter_type = request.GET.get('filter', 'month_range')

    # Defaults
    selected_month_from = current_month
    selected_year_from = current_year
    selected_month_to = current_month
    selected_year_to = current_year

    if filter_type == 'today':
        filter_start = today
        filter_end = today
    else:
        # Default is month_range
        filter_type = 'month_range'
        try:
            selected_month_from = int(request.GET.get('month_from', current_month))
            selected_year_from = int(request.GET.get('year_from', current_year))
            selected_month_to = int(request.GET.get('month_to', current_month))
            selected_year_to = int(request.GET.get('year_to', current_year))
        except ValueError:
            selected_month_from = current_month
            selected_year_from = current_year
            selected_month_to = current_month
            selected_year_to = current_year

        import calendar
        d1 = date(selected_year_from, selected_month_from, 1)
        _, last_day_to = calendar.monthrange(selected_year_to, selected_month_to)
        d2 = date(selected_year_to, selected_month_to, last_day_to)
        
        if d1 > d2:
            filter_start = date(selected_year_to, selected_month_to, 1)
            _, last_day_from = calendar.monthrange(selected_year_from, selected_month_from)
            filter_end = date(selected_year_from, selected_month_from, last_day_from)
            # Swap for context variables
            selected_month_from, selected_year_from, selected_month_to, selected_year_to = (
                selected_month_to, selected_year_to, selected_month_from, selected_year_from
            )
        else:
            filter_start = d1
            filter_end = d2"""

# There's a slight formatting difference in print_cashier_remittance vs cashier_income_dashboard
date_logic_print_original = """    # --- Date filter from GET params ---
    date_from_str = request.GET.get('date_from', '')
    date_to_str = request.GET.get('date_to', '')
    filter_type = request.GET.get('filter', 'month')

    if filter_type == 'today':
        filter_start = today
        filter_end = today
        selected_month = current_month
        selected_year = current_year
    elif filter_type == 'custom' and date_from_str and date_to_str:
        try:
            filter_start = datetime.strptime(date_from_str, '%Y-%m-%d').date()
            filter_end = datetime.strptime(date_to_str, '%Y-%m-%d').date()
        except ValueError:
            filter_start = date(current_year, current_month, 1)
            filter_end = today
        selected_month = current_month
        selected_year = current_year
    else:
        filter_type = 'month'
        month_param = request.GET.get('month')
        year_param = request.GET.get('year')
        if month_param and year_param:
            try:
                selected_month = int(month_param)
                selected_year = int(year_param)
            except ValueError:
                selected_month = current_month
                selected_year = current_year
        else:
            selected_month = current_month
            selected_year = current_year

        import calendar
        _, last_day = calendar.monthrange(selected_year, selected_month)
        filter_start = date(selected_year, selected_month, 1)
        filter_end = date(selected_year, selected_month, last_day)"""

views_code = views_code.replace(date_logic_original, date_logic_new)
views_code = views_code.replace(date_logic_print_original, date_logic_new)

# Update context bindings in dashboard_views
views_code = views_code.replace("'selected_month': selected_month,", "'month_from': selected_month_from, 'year_from': selected_year_from, 'month_to': selected_month_to, 'year_to': selected_year_to,")
views_code = views_code.replace("'selected_year': selected_year,", "")
views_code = views_code.replace("'date_from': date_from_str or filter_start.strftime('%Y-%m-%d'),", "")
views_code = views_code.replace("'date_to': date_to_str or filter_end.strftime('%Y-%m-%d'),", "")

# Remove include_names logic
print_include_names_old = """    include_names = request.GET.get('include_names', '0') == '1'

    # Retrieve totals for this user"""
views_code = views_code.replace(print_include_names_old, "    # Retrieve totals for this user")

print_consumers_old = """    # Get consumers processed
    consumers_list = []
    if include_names:
        from django.db.models import Count
        my_payments = Payment.objects.filter(
            payment_date__date__gte=filter_start,
            payment_date__date__lte=filter_end,
            processed_by=target_user
        )
        
        consumer_totals = my_payments.values(
            'bill__consumer__first_name', 
            'bill__consumer__last_name', 
            'bill__consumer__id_number',
        ).annotate(
            total_paid=Sum('amount_paid'),
            txn_count=Count('id')
        ).order_by('-total_paid')

        for ct in consumer_totals:
            consumers_list.append({
                'full_name': f"{ct['bill__consumer__first_name']} {ct['bill__consumer__last_name']}",
                'id_number': ct['bill__consumer__id_number'],
                'total_paid': ct['total_paid'],
                'txn_count': ct['txn_count']
            })"""
            
print_consumers_new = """    # Get consumers processed
    consumers_list = []
    from django.db.models import Count
    my_payments = Payment.objects.filter(
        payment_date__date__gte=filter_start,
        payment_date__date__lte=filter_end,
        processed_by=target_user
    )
    
    consumer_totals = my_payments.values(
        'bill__consumer__first_name', 
        'bill__consumer__last_name', 
        'bill__consumer__id_number',
    ).annotate(
        total_paid=Sum('amount_paid'),
        txn_count=Count('id')
    ).order_by('-total_paid')

    for ct in consumer_totals:
        consumers_list.append({
            'full_name': f"{ct['bill__consumer__first_name']} {ct['bill__consumer__last_name']}",
            'id_number': ct['bill__consumer__id_number'],
            'total_paid': ct['total_paid'],
            'txn_count': ct['txn_count']
        })"""
views_code = views_code.replace(print_consumers_old, print_consumers_new)
views_code = views_code.replace("'include_names': include_names,", "")

with open(dashboard_views, 'w', encoding='utf-8') as f:
    f.write(views_code)


# 2. Update cashier_income.html date filter and print button
with open(cashier_income, 'r', encoding='utf-8') as f:
    tmpl = f.read()

form_selects_old = """            <div class="flex items-end gap-2 flex-wrap border-l border-light-200 pl-4 ml-2">
                <div>
                    <label class="block text-xs text-dark-500 font-medium mb-1 uppercase tracking-wider">Select Month</label>
                    <div class="flex items-center gap-2">
                        <select name="month" class="px-3 py-2 border border-light-300 rounded-lg text-sm text-dark-800 bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500 min-w-[120px]">
                            <option value="1" {% if selected_month|floatformat:"0" == "1" %}selected{% endif %}>January</option>
                            <option value="2" {% if selected_month|floatformat:"0" == "2" %}selected{% endif %}>February</option>
                            <option value="3" {% if selected_month|floatformat:"0" == "3" %}selected{% endif %}>March</option>
                            <option value="4" {% if selected_month|floatformat:"0" == "4" %}selected{% endif %}>April</option>
                            <option value="5" {% if selected_month|floatformat:"0" == "5" %}selected{% endif %}>May</option>
                            <option value="6" {% if selected_month|floatformat:"0" == "6" %}selected{% endif %}>June</option>
                            <option value="7" {% if selected_month|floatformat:"0" == "7" %}selected{% endif %}>July</option>
                            <option value="8" {% if selected_month|floatformat:"0" == "8" %}selected{% endif %}>August</option>
                            <option value="9" {% if selected_month|floatformat:"0" == "9" %}selected{% endif %}>September</option>
                            <option value="10" {% if selected_month|floatformat:"0" == "10" %}selected{% endif %}>October</option>
                            <option value="11" {% if selected_month|floatformat:"0" == "11" %}selected{% endif %}>November</option>
                            <option value="12" {% if selected_month|floatformat:"0" == "12" %}selected{% endif %}>December</option>
                        </select>
                        <select name="year" class="px-3 py-2 border border-light-300 rounded-lg text-sm text-dark-800 bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500 w-[90px]">
                            <option value="2024" {% if selected_year|floatformat:"0" == "2024" %}selected{% endif %}>2024</option>
                            <option value="2025" {% if selected_year|floatformat:"0" == "2025" %}selected{% endif %}>2025</option>
                            <option value="2026" {% if selected_year|floatformat:"0" == "2026" %}selected{% endif %}>2026</option>
                            <option value="2027" {% if selected_year|floatformat:"0" == "2027" %}selected{% endif %}>2027</option>
                            <option value="2028" {% if selected_year|floatformat:"0" == "2028" %}selected{% endif %}>2028</option>
                        </select>
                        <button type="submit" name="filter" value="month" title="Filter by Month"
                                class="px-3 py-2 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 hover:text-emerald-800 border border-emerald-200 rounded-lg text-sm font-semibold transition-colors flex items-center h-full">
                            <i class="bi bi-funnel-fill"></i>
                        </button>
                    </div>
                </div>
            </div>

            <!-- Custom Date Group -->
            <div class="flex items-end gap-2 flex-wrap border-l border-light-200 pl-4 ml-2">
                <div>
                    <label class="block text-xs text-dark-500 font-medium mb-1 uppercase tracking-wider">Custom Range</label>
                    <div class="flex items-center gap-2">
                        <input type="date" name="date_from" id="date_from" value="{{ date_from }}"
                               class="px-3 py-2 text-sm border border-light-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 bg-white text-dark-800 w-[135px]">
                        <span class="text-dark-400 text-sm">to</span>
                        <input type="date" name="date_to" id="date_to" value="{{ date_to }}"
                               class="px-3 py-2 text-sm border border-light-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 bg-white text-dark-800 w-[135px]">
                        <button type="submit" name="filter" value="custom" title="Filter by Date Range"
                                class="px-3 py-2 bg-dark-800 hover:bg-dark-900 text-white rounded-lg text-sm font-semibold transition-colors flex items-center h-full">
                            <i class="bi bi-search"></i>
                        </button>
                    </div>
                </div>
            </div>"""

form_selects_new = """            <!-- Range Group -->
            <div class="flex items-end gap-2 flex-wrap border-l border-light-200 pl-4 ml-2">
                <div>
                    <label class="block text-xs text-dark-500 font-medium mb-1 uppercase tracking-wider">From Month</label>
                    <div class="flex items-center gap-2">
                        <select name="month_from" class="px-3 py-2 border border-light-300 rounded-lg text-sm text-dark-800 bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500 min-w-[120px]">
                            <option value="1" {% if month_from|floatformat:"0" == "1" %}selected{% endif %}>January</option>
                            <option value="2" {% if month_from|floatformat:"0" == "2" %}selected{% endif %}>February</option>
                            <option value="3" {% if month_from|floatformat:"0" == "3" %}selected{% endif %}>March</option>
                            <option value="4" {% if month_from|floatformat:"0" == "4" %}selected{% endif %}>April</option>
                            <option value="5" {% if month_from|floatformat:"0" == "5" %}selected{% endif %}>May</option>
                            <option value="6" {% if month_from|floatformat:"0" == "6" %}selected{% endif %}>June</option>
                            <option value="7" {% if month_from|floatformat:"0" == "7" %}selected{% endif %}>July</option>
                            <option value="8" {% if month_from|floatformat:"0" == "8" %}selected{% endif %}>August</option>
                            <option value="9" {% if month_from|floatformat:"0" == "9" %}selected{% endif %}>September</option>
                            <option value="10" {% if month_from|floatformat:"0" == "10" %}selected{% endif %}>October</option>
                            <option value="11" {% if month_from|floatformat:"0" == "11" %}selected{% endif %}>November</option>
                            <option value="12" {% if month_from|floatformat:"0" == "12" %}selected{% endif %}>December</option>
                        </select>
                        <select name="year_from" class="px-3 py-2 border border-light-300 rounded-lg text-sm text-dark-800 bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500 w-[90px]">
                            <option value="2024" {% if year_from|floatformat:"0" == "2024" %}selected{% endif %}>2024</option>
                            <option value="2025" {% if year_from|floatformat:"0" == "2025" %}selected{% endif %}>2025</option>
                            <option value="2026" {% if year_from|floatformat:"0" == "2026" %}selected{% endif %}>2026</option>
                            <option value="2027" {% if year_from|floatformat:"0" == "2027" %}selected{% endif %}>2027</option>
                            <option value="2028" {% if year_from|floatformat:"0" == "2028" %}selected{% endif %}>2028</option>
                        </select>
                    </div>
                </div>
                
                <span class="text-dark-400 text-sm mb-2 px-1">to</span>

                <div>
                    <label class="block text-xs text-dark-500 font-medium mb-1 uppercase tracking-wider">To Month</label>
                    <div class="flex items-center gap-2">
                        <select name="month_to" class="px-3 py-2 border border-light-300 rounded-lg text-sm text-dark-800 bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500 min-w-[120px]">
                            <option value="1" {% if month_to|floatformat:"0" == "1" %}selected{% endif %}>January</option>
                            <option value="2" {% if month_to|floatformat:"0" == "2" %}selected{% endif %}>February</option>
                            <option value="3" {% if month_to|floatformat:"0" == "3" %}selected{% endif %}>March</option>
                            <option value="4" {% if month_to|floatformat:"0" == "4" %}selected{% endif %}>April</option>
                            <option value="5" {% if month_to|floatformat:"0" == "5" %}selected{% endif %}>May</option>
                            <option value="6" {% if month_to|floatformat:"0" == "6" %}selected{% endif %}>June</option>
                            <option value="7" {% if month_to|floatformat:"0" == "7" %}selected{% endif %}>July</option>
                            <option value="8" {% if month_to|floatformat:"0" == "8" %}selected{% endif %}>August</option>
                            <option value="9" {% if month_to|floatformat:"0" == "9" %}selected{% endif %}>September</option>
                            <option value="10" {% if month_to|floatformat:"0" == "10" %}selected{% endif %}>October</option>
                            <option value="11" {% if month_to|floatformat:"0" == "11" %}selected{% endif %}>November</option>
                            <option value="12" {% if month_to|floatformat:"0" == "12" %}selected{% endif %}>December</option>
                        </select>
                        <select name="year_to" class="px-3 py-2 border border-light-300 rounded-lg text-sm text-dark-800 bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500 w-[90px]">
                            <option value="2024" {% if year_to|floatformat:"0" == "2024" %}selected{% endif %}>2024</option>
                            <option value="2025" {% if year_to|floatformat:"0" == "2025" %}selected{% endif %}>2025</option>
                            <option value="2026" {% if year_to|floatformat:"0" == "2026" %}selected{% endif %}>2026</option>
                            <option value="2027" {% if year_to|floatformat:"0" == "2027" %}selected{% endif %}>2027</option>
                            <option value="2028" {% if year_to|floatformat:"0" == "2028" %}selected{% endif %}>2028</option>
                        </select>
                        <button type="submit" name="filter" value="month_range" title="Filter by Range"
                                class="px-3 py-2 bg-emerald-600 text-white hover:bg-emerald-700 rounded-lg text-sm font-semibold transition-colors flex items-center h-full">
                            <i class="bi bi-funnel-fill"></i>
                        </button>
                    </div>
                </div>
            </div>"""
tmpl = tmpl.replace(form_selects_old, form_selects_new)

# Update buttons
buttons_old = """                <div class="px-4 pb-3 flex gap-2">
                    <a href="{% url 'consumers:print_cashier_remittance' cashier.user_id %}?date_from={{ filter_start|date:'Y-m-d' }}&date_to={{ filter_end|date:'Y-m-d' }}&filter={{ filter_type }}&month={{ selected_month }}&year={{ selected_year }}&include_names=0"
                       target="_blank"
                       class="w-1/2 flex items-center justify-center gap-1.5 px-2 py-2 bg-white hover:bg-light-50 border border-light-300 text-dark-700 hover:text-dark-900 text-[11px] font-bold rounded-lg transition-colors">
                        <i class="bi bi-printer text-dark-500"></i>
                        Print Summary
                    </a>
                    <a href="{% url 'consumers:print_cashier_remittance' cashier.user_id %}?date_from={{ filter_start|date:'Y-m-d' }}&date_to={{ filter_end|date:'Y-m-d' }}&filter={{ filter_type }}&month={{ selected_month }}&year={{ selected_year }}&include_names=1"
                       target="_blank"
                       class="w-1/2 flex items-center justify-center gap-1.5 px-2 py-2 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 text-emerald-700 hover:text-emerald-800 text-[11px] font-bold rounded-lg transition-colors">
                        <i class="bi bi-printer-fill text-emerald-600"></i>
                        Print Detailed
                    </a>
                </div>"""
buttons_new = """                <div class="px-4 pb-3 flex gap-2">
                    <a href="{% url 'consumers:print_cashier_remittance' cashier.user_id %}?filter={{ filter_type }}&month_from={{ month_from }}&year_from={{ year_from }}&month_to={{ month_to }}&year_to={{ year_to }}"
                       target="_blank"
                       class="w-full flex items-center justify-center gap-1.5 px-2 py-2 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 text-emerald-700 hover:text-emerald-800 text-[12px] font-bold rounded-lg transition-colors">
                        <i class="bi bi-printer-fill text-emerald-600"></i>
                        Print Summary
                    </a>
                </div>"""
tmpl = tmpl.replace(buttons_old, buttons_new)

with open(cashier_income, 'w', encoding='utf-8') as f:
    f.write(tmpl)

# 3. Update print_cashier_remittance.html
with open(print_remit_tmpl, 'r', encoding='utf-8') as f:
    ptmpl = f.read()

# Remove if include_names block boundaries and else logic
ptmpl = ptmpl.replace("{% if include_names %}", "")

else_block = """        {% else %}
            <div style="text-align: center; margin-top: 40px; padding: 30px; background: #f8fcf8; border: 1px dashed #a3e635;">
                <h2 style="font-size: 24px; color: #15803d; margin-bottom: 5px;">REMITTANCE CLEARANCE</h2>
                <p>The total amount to be remitted by the collector for this period is <strong>&#8369;{{ period_total|floatformat:2|intcomma }}</strong>.</p>
                <p style="font-size: 10px; color: #777; margin-top: 10px;">Consumer breakdown omitted by request.</p>
            </div>
        {% endif %}"""
ptmpl = ptmpl.replace(else_block, "")
ptmpl = ptmpl.replace("{% elif filter_type == 'month' %}", "{% elif filter_type == 'month_range' and month_from == month_to and year_from == year_to %}")

with open(print_remit_tmpl, 'w', encoding='utf-8') as f:
    f.write(ptmpl)

print("Updates applied successfully.")
