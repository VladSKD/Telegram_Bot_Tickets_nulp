import React, { useState, useRef } from 'react';
import './App.css';

export default function App() {
  const [seats, setSeats] = useState([]);
  const [currentZone, setCurrentZone] = useState('Партер');
  
  // Встановлюємо оригінальні розміри полотна Контрамарки за замовчуванням
  const [baseSize] = useState({ width: 4600, height: 3481 }); 
  const containerRef = useRef(null);
  const fileInputRef = useRef(null);

  const handleContainerClick = (e) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    
    // Вираховуємо коефіцієнт масштабування між реальним розміром div та внутрішнім viewBox
    const scaleX = baseSize.width / rect.width;
    const scaleY = baseSize.height / rect.height;

    // Переводимо координати кліку в абсолютні координати 4600x3481
    const x = Math.round((e.clientX - rect.left) * scaleX);
    const y = Math.round((e.clientY - rect.top) * scaleY);

    const newSeat = {
      id: `manual-${currentZone}-${Date.now()}`,
      cx: x,
      cy: y,
      zone: currentZone,
      type: 'manual', 
      status: 'available'
    };

    setSeats([...seats, newSeat]);
  };

  const handleDotClick = (e, idToRemove) => {
    e.stopPropagation();
    setSeats(seats.filter(seat => seat.id !== idToRemove));
  };

  const copyToClipboard = () => {
    navigator.clipboard.writeText(JSON.stringify(seats, null, 2));
    alert('Масив координат скопійовано в буфер обміну!');
  };

  const undoLast = () => {
    setSeats(seats.slice(0, -1));
  };

  const clearAll = () => {
    if (window.confirm('Ви впевнені, що хочете видалити всі місця?')) {
      setSeats([]);
    }
  };

  const handleFileUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const parsedData = JSON.parse(event.target.result);
        
        // ВАРІАНТ 1: Це оригінальний "сирий" файл Контрамарки (kpnta.json)
        if (parsedData.data && parsedData.data.sectors) {
          let extractedSeats = [];
          parsedData.data.sectors.forEach((sector, sIdx) => {
            const sectorName = sector.name || 'Unknown';
            (sector.rows || []).forEach((row, rIdx) => {
              const rowNum = row.number || '';
              (row.places || []).forEach((place, pIdx) => {
                extractedSeats.push({
                  id: `kontra-raw-${sIdx}-${rIdx}-${pIdx}`,
                  cx: place.x,
                  cy: place.y,
                  zone: sectorName,
                  row: rowNum,
                  seatNum: place.number,
                  type: 'kontramarka', 
                  status: 'available'
                });
              });
            });
          });
          setSeats(extractedSeats);
          alert(`Успішно завантажено ${extractedSeats.length} місць з оригінального файлу!`);
        } 
        // ВАРІАНТ 2: Це масив (наш спрощений файл або старий бекап)
        else if (Array.isArray(parsedData)) {
          if (parsedData.length > 0 && parsedData[0].hasOwnProperty('sector') && parsedData[0].hasOwnProperty('x')) {
            const convertedSeats = parsedData.map((item, index) => ({
              id: `kontra-simple-${item.sector}-${item.row}-${item.seat}-${index}`,
              cx: item.x,
              cy: item.y,
              zone: item.sector,
              row: item.row,
              seatNum: item.seat,
              type: 'kontramarka', 
              status: 'available'
            }));
            setSeats(convertedSeats);
            alert(`Успішно завантажено ${convertedSeats.length} місць зі спрощеного файлу!`);
          } else {
            setSeats(parsedData); // Якщо це старий бекап з cx/cy
          }
        } 
        // ВАРІАНТ 3: Це формат OpenCV
        else if (typeof parsedData === 'object' && parsedData !== null) {
          let convertedSeats = [];
          let idCounter = 1;

          const extractOpenCVData = (array, elementType) => {
            if (Array.isArray(array)) {
              array.forEach(item => {
                convertedSeats.push({
                  id: `opencv-${elementType}-${idCounter++}`,
                  cx: item.x,
                  cy: item.y,
                  zone: 'Авто-імпорт',
                  type: elementType,
                  status: elementType === 'blocked_seats' ? 'blocked' : 'available'
                });
              });
            }
          };

          extractOpenCVData(parsedData.available_seats, 'available_seats');
          extractOpenCVData(parsedData.blocked_seats, 'blocked_seats');
          extractOpenCVData(parsedData.yellow_lodges, 'yellow_lodges');
          extractOpenCVData(parsedData.black_pillars, 'black_pillars');

          setSeats(convertedSeats);
        }
      } catch (error) {
        alert('Помилка при читанні JSON файлу. Перевірте формат.');
        console.error(error);
      }
    };
    reader.readAsText(file);
    if (fileInputRef.current) fileInputRef.current.value = ''; // Скидаємо інпут
  };

  // Трохи яскравіші кольори для темного фону
  const getFillColor = (type) => {
    switch(type) {
      case 'yellow_lodges': return '#fbbf24';   
      case 'black_pillars': return '#9ca3af';    
      case 'available_seats': return '#60a5fa';
      case 'blocked_seats': return '#f87171';   
      case 'manual': return '#4ade80';          
      case 'kontramarka': return '#c084fc'; // Світло-фіолетовий
      default: return '#f87171';
    }
  };

  return (
    <div style={{ 
      padding: '30px', 
      minHeight: '100vh', 
      background: 'linear-gradient(135deg, #1e1e24, #2b2d42)', // Темний градієнт
      color: '#fff',
      fontFamily: 'system-ui, -apple-system, sans-serif'
    }}>
      
      {/* Панель керування Glassmorphism */}
      <div style={{ 
        marginBottom: '30px', 
        display: 'flex', 
        flexWrap: 'wrap', 
        gap: '15px', 
        alignItems: 'center', 
        justifyContent: 'center',
        background: 'rgba(255, 255, 255, 0.05)',
        backdropFilter: 'blur(16px)',
        WebkitBackdropFilter: 'blur(16px)',
        border: '1px solid rgba(255, 255, 255, 0.1)',
        boxShadow: '0 8px 32px 0 rgba(0, 0, 0, 0.3)',
        borderRadius: '16px',
        padding: '20px'
      }}>
        <input 
          type="text" 
          value={currentZone} 
          onChange={(e) => setCurrentZone(e.target.value)} 
          style={{ 
            padding: '10px 15px', 
            borderRadius: '8px', 
            border: '1px solid rgba(255,255,255,0.2)', 
            background: 'rgba(0,0,0,0.2)',
            color: '#fff',
            outline: 'none'
          }}
          placeholder="Назва зони"
        />
        <button onClick={undoLast} style={btnStyle}>Скасувати останній</button>
        <button onClick={clearAll} style={{...btnStyle, background: 'rgba(239, 68, 68, 0.2)', color: '#fca5a5', borderColor: 'rgba(239, 68, 68, 0.3)'}}>Очистити всі</button>
        <button onClick={copyToClipboard} style={{...btnStyle, background: '#3b82f6', color: '#fff', border: 'none'}}>
          Скопіювати JSON ({seats.length})
        </button>

        <div style={{ display: 'flex', alignItems: 'center', gap: '15px', paddingLeft: '20px', borderLeft: '1px solid rgba(255,255,255,0.2)' }}>
          <label style={{ fontWeight: '500', color: '#e2e8f0' }}>Завантажити JSON:</label>
          <input 
            type="file" 
            accept=".json,application/json" 
            onChange={handleFileUpload} 
            ref={fileInputRef} 
            style={{ color: '#94a3b8' }}
          />
        </div>
      </div>

      {/* Робоча область (Чиста геометрія) */}
      <div 
        ref={containerRef}
        onClick={handleContainerClick}
        style={{ 
          position: 'relative', 
          width: '100%', 
          maxWidth: '1200px', // Ширина контейнера на екрані
          aspectRatio: `${baseSize.width} / ${baseSize.height}`, // Зберігаємо точні пропорції Опери
          margin: '0 auto', 
          background: '#121214', // Глибокий темний фон для контрасту
          border: '1px solid rgba(255,255,255,0.05)',
          borderRadius: '12px',
          boxShadow: 'inset 0 0 40px rgba(0,0,0,0.5), 0 20px 40px rgba(0,0,0,0.4)',
          cursor: 'crosshair',
          overflow: 'hidden'
        }}
      >
        <svg 
          viewBox={`0 0 ${baseSize.width} ${baseSize.height}`} 
          style={{ width: '100%', height: '100%' }}
        >
          {/* Малюємо місця */}
          {seats.map((seat) => (
            <circle 
              key={seat.id} 
              cx={seat.cx} 
              cy={seat.cy} 
              r="18" // Великий радіус, щоб точки було видно на масивному полотні
              fill={getFillColor(seat.type)} 
              stroke="#121214" // Обведення кольором фону
              strokeWidth="4" 
              onClick={(e) => handleDotClick(e, seat.id)}
              style={{ cursor: 'pointer', transition: 'all 0.2s ease' }}
            />
          ))}
        </svg>
      </div>
    </div>
  );
}

// Загальний стиль для кнопок
const btnStyle = {
  padding: '10px 20px',
  borderRadius: '8px',
  border: '1px solid rgba(255,255,255,0.2)',
  background: 'rgba(255,255,255,0.1)',
  color: '#e2e8f0',
  cursor: 'pointer',
  fontWeight: '500',
  transition: 'all 0.2s ease'
};й
