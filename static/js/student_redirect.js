// Скрипт для перенаправления студентов на их личное расписание
document.addEventListener('DOMContentLoaded', function() {
    // Проверяем, является ли пользователь студентом
    const isStudent = document.body.classList.contains('user-student');
    
    if (isStudent) {
        // Находим все ссылки на общее расписание и меняем их на ссылки на личное расписание
        const scheduleLinks = document.querySelectorAll('a[href="/schedule/"]');
        scheduleLinks.forEach(link => {
            link.href = '/classes/student/schedule/';
            
            // Если в ссылке есть текст "Расписание", меняем его на "Моё расписание"
            if (link.textContent.trim() === 'Расписание') {
                // Сохраняем иконку и её классы, если она есть
                const icon = link.querySelector('i');
                if (icon) {
                    // Сохраняем классы иконки
                    const iconClasses = icon.className;
                    link.innerHTML = '';
                    // Создаем новую иконку с теми же классами
                    const newIcon = document.createElement('i');
                    newIcon.className = iconClasses;
                    link.appendChild(newIcon);
                    link.appendChild(document.createTextNode(' Моё расписание'));
                } else {
                    link.textContent = 'Моё расписание';
                }
            }
        });
        
        // Перехватываем все ссылки на расписание
        document.querySelectorAll('a').forEach(link => {
            // Проверяем ссылки на общее расписание или с текстом "Полное расписание"
            const linkText = link.textContent.trim();
            const linkHref = link.href;
            
            // Перенаправляем ссылки на общее расписание
            if (linkHref === window.location.origin + '/schedule/' || 
                linkText === 'Полное расписание' || 
                linkText.includes('Полное расписание')) {
                
                link.href = '/classes/student/schedule/';
                
                // Если это ссылка в навигации с текстом "Расписание", меняем ее на "Моё расписание"
                if (linkText === 'Расписание') {
                    const icon = link.querySelector('i');
                    if (icon) {
                        // Сохраняем классы иконки
                        const iconClasses = icon.className;
                        link.innerHTML = '';
                        // Создаем новую иконку с теми же классами
                        const newIcon = document.createElement('i');
                        newIcon.className = iconClasses;
                        link.appendChild(newIcon);
                        link.appendChild(document.createTextNode(' Моё расписание'));
                    } else {
                        link.textContent = 'Моё расписание';
                    }
                }
            }
        });
    }
});
