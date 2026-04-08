import ast
import os
import shutil

VIEWS_PATH = 'd:/balilihan_waterworks/waterworks/consumers/views.py'
VIEWS_DIR = 'd:/balilihan_waterworks/waterworks/consumers/views'

if not os.path.exists(VIEWS_DIR):
    os.makedirs(VIEWS_DIR)

with open(VIEWS_PATH, 'r', encoding='utf-8') as f:
    source = f.read()

lines = source.split('\n')
tree = ast.parse(source)

# We want to identify the global imports and helpers
# They are generally before line 132 or so.
# Let's find the last global import.
global_end_line = 0
for node in tree.body:
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        global_end_line = max(global_end_line, node.end_lineno)

# Wait, there are helper functions too: `authenticate_api_request`, `get_previous_reading`, `calculate_water_bill`.
# Let's include them in the global block, up to the first actual view.
# The first view seems to be 'api_submit_reading' or similar. We can just collect all functions that are 'helpers'.

helpers = ['authenticate_api_request', 'get_previous_reading', 'calculate_water_bill']

# Categorize functions
categories = {
    'auth_views': ['staff_login', 'staff_logout', 'forgot_password_request', 'forgot_username', 'account_recovery', 'password_reset_confirm', 'password_reset_complete'],
    'profile_views': ['edit_profile'],
    'dashboard_views': ['home', 'home_print'],
    'consumer_views': ['consumer_management', 'add_consumer', 'consumer_list', 'consumer_detail', 'edit_consumer', 'consumer_bill', 'import_consumers_csv', 'download_consumer_template', 'connected_consumers', 'disconnected_consumers_list', 'disconnect_consumer', 'reconnect_consumer', 'delinquent_consumers', 'export_delinquent_consumers', 'delinquent_report_printable', 'load_puroks'],
    'meter_views': ['meter_reading_overview', 'meter_readings', 'meter_readings_print', 'barangay_meter_readings', 'barangay_meter_readings_print', 'confirm_all_readings', 'confirm_all_readings_global', 'export_barangay_readings', 'confirm_reading', 'reject_reading', 'pending_readings_view', 'confirm_selected_readings'],
    'api_views': ['api_login', 'api_logout', 'api_consumers', 'api_get_previous_reading', 'api_get_consumer_bill', 'api_get_consumer_bills', 'api_submit_reading', 'api_get_current_rates', 'api_get_system_settings', 'api_check_settings_version', 'api_submit_manual_reading', 'api_get_pending_readings', 'api_confirm_reading', 'api_reject_reading', 'api_get_notifications', 'api_get_notification_count', 'api_mark_notification_read', 'smart_meter_webhook'],
    'report_views': ['reports', 'barangay_report', 'export_report_excel'],
    'payment_views': ['inquire', 'process_payment', 'water_bill_print', 'payment_receipt', 'payment_history'],
    'admin_views': ['system_settings_verification', 'system_management', 'backup_database', 'database_documentation', 'admin_verification', 'user_login_history', 'user_specific_login_history', 'session_activities', 'user_management', 'create_user', 'edit_user', 'delete_user', 'reset_user_password', 'test_email'],
    'notification_views': ['mark_notification_read', 'mark_all_notifications_read']
}

# Add any missed functions to a 'misc_views'
categorized_funcs = set()
for funcs in categories.values():
    categorized_funcs.update(funcs)

header_nodes = []
view_nodes = []

for node in tree.body:
    if isinstance(node, ast.FunctionDef):
        if node.name in helpers:
            header_nodes.append(node)
        else:
            view_nodes.append(node)
    elif isinstance(node, (ast.Import, ast.ImportFrom, ast.Assign, ast.Expr)):
        # keep as header if it's before the first view
        if not view_nodes:
            header_nodes.append(node)

# Header text
header_lines = []
last_header_line = header_nodes[-1].end_lineno if header_nodes else 0
header_text = '\n'.join(lines[0:last_header_line])

# Now distribute the views and their preceding comments/decorators
def get_node_text(node):
    start = node.lineno - 1
    # include decorators
    if node.decorator_list:
        start = node.decorator_list[0].lineno - 1
    
    # backtrack for comments
    while start > last_header_line and lines[start-1].strip().startswith('#'):
        start -= 1
        
    # include empty lines before comments
    while start > last_header_line and lines[start-1].strip() == '':
        start -= 1
        
    end = node.end_lineno
    return '\n'.join(lines[start:end])

files_content = {k: [header_text, ""] for k in categories.keys()}
files_content['misc_views'] = [header_text, ""]

for node in view_nodes:
    func_name = node.name
    target_category = 'misc_views'
    for cat, funcs in categories.items():
        if func_name in funcs:
            target_category = cat
            break
            
    files_content[target_category].append(get_node_text(node))
    files_content[target_category].append("")

# Write files
all_modules = []
for cat, content_blocks in files_content.items():
    if len(content_blocks) > 2: # means it has views
        filepath = os.path.join(VIEWS_DIR, f"{cat}.py")
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(content_blocks))
        all_modules.append(cat)
        print(f"Created {cat}.py")

# Create __init__.py
init_path = os.path.join(VIEWS_DIR, '__init__.py')
with open(init_path, 'w', encoding='utf-8') as f:
    for mod in all_modules:
        f.write(f"from .{mod} import *\n")

print("__init__.py created.")
