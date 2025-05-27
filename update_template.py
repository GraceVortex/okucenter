import re

# Read the current template
with open('templates/core/home.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Read the new student dashboard
with open('new_student_dashboard.html', 'r', encoding='utf-8') as f:
    new_dashboard = f.read()

# Find the student section in the current template
pattern = r'{% elif user.is_student %}.*?{% elif user.is_parent %}'
student_section = re.search(pattern, content, re.DOTALL).group(0)

# Replace with the new dashboard (keeping the elif user.is_parent part)
new_content = content.replace(student_section, new_dashboard + '\n        {% elif user.is_parent %}')

# Write the updated content back to the template
with open('templates/core/home.html', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Template updated successfully!")
