/**
 * Отладочный код для Face ID
 */

// Добавляем обработчик события DOMContentLoaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('Отладочный скрипт загружен');
    
    // Находим кнопку "Распознать"
    const recognizeBtn = document.getElementById('recognize-btn');
    
    if (recognizeBtn) {
        console.log('Кнопка "Распознать" найдена');
        
        // Добавляем обработчик события click
        recognizeBtn.addEventListener('click', function() {
            console.log('Кнопка "Распознать" нажата');
            
            // Находим элементы для отображения результатов
            const recognitionResult = document.getElementById('recognition-result');
            const classItemsContainer = document.getElementById('class-items-container');
            const noClassesMessage = document.getElementById('no-classes-message');
            
            console.log('Элементы для отображения результатов:', {
                recognitionResult: recognitionResult ? 'найден' : 'не найден',
                classItemsContainer: classItemsContainer ? 'найден' : 'не найден',
                noClassesMessage: noClassesMessage ? 'найден' : 'не найден'
            });
            
            // Проверяем стили элементов
            if (recognitionResult) {
                console.log('Стиль recognitionResult.style.display =', recognitionResult.style.display);
            }
            
            // Через 5 секунд после нажатия на кнопку проверяем, отображаются ли результаты
            setTimeout(function() {
                console.log('Проверка отображения результатов через 5 секунд:');
                
                if (recognitionResult) {
                    console.log('recognitionResult.style.display =', recognitionResult.style.display);
                }
                
                if (classItemsContainer) {
                    console.log('classItemsContainer.innerHTML =', classItemsContainer.innerHTML);
                    console.log('classItemsContainer.childElementCount =', classItemsContainer.childElementCount);
                }
                
                if (noClassesMessage) {
                    console.log('noClassesMessage.style.display =', noClassesMessage.style.display);
                }
            }, 5000);
        });
    } else {
        console.error('Кнопка "Распознать" не найдена');
    }
});
