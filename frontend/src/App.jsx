import { useState, useEffect } from 'react';
import './App.css';

const tg = window.Telegram.WebApp;

function App() {
  const [selectedSeats, setSelectedSeats] = useState([]);
  
  // ТЕСТОВІ ДАНІ: Імітуємо зайняті місця (червоні)
  // У майбутньому ці дані ти будеш передавати з Python через параметри URL або API
  const occupiedSeats = ['6-4', '7-3', '12-1', '12-2', '12-3', '1-6', '2-11', '24-1'];

  useEffect(() => {
    tg.expand();
    tg.ready();
  }, []);

  useEffect(() => {
    if (selectedSeats.length > 0) {
      tg.MainButton.text = `ПІДТВЕРДИТИ (${selectedSeats.length} шт.)`;
      tg.MainButton.show();
    } else {
      tg.MainButton.hide();
    }

    const handleMainButtonClick = () => {
      tg.sendData(JSON.stringify(selectedSeats));
      tg.close();
    };

    tg.MainButton.onClick(handleMainButtonClick);
    return () => tg.MainButton.offClick(handleMainButtonClick);
  }, [selectedSeats]);

  const toggleSeat = (row, seatNum) => {
    const seatId = `${row}-${seatNum}`;
    
    // Блокуємо клік, якщо місце зайняте
    if (occupiedSeats.includes(seatId)) return;

    setSelectedSeats(prev => {
      if (prev.some(s => s.id === seatId)) {
        return prev.filter(s => s.id !== seatId);
      }
      return [...prev, { id: seatId, row, seat: seatNum }];
    });
  };

  // Конфігурація залу (зверху вниз)
  // left: к-сть місць зліва, right: к-сть місць справа
  const hallConfig = [
    { row: '24', left: 3, right: 3 }, { row: '23', left: 3, right: 3 },
    { row: '22', left: 3, right: 3 }, { row: '21', left: 3, right: 3 },
    { row: '20', left: 3, right: 3 }, { row: '19', left: 3, right: 3 },
    { row: '18', left: 3, right: 3 }, { row: '17', left: 3, right: 3 },
    { row: '16', left: 3, right: 3 }, { row: '15', left: 3, right: 3 },
    { row: '14', left: 3, right: 3 },
    { isAisle: true, label: '' },
    { row: '13', left: 6, right: 6 },
    { isAisle: true, label: 'ПРОХІД' },
    { row: '12Б', left: 6, right: 6 }, { row: '12А', left: 6, right: 6 },
    { row: '12', left: 6, right: 6 }, { row: '11', left: 6, right: 6 },
    { row: '10', left: 6, right: 6 }, { row: '9', left: 6, right: 6 },
    { row: '8', left: 6, right: 6 }, { row: '7', left: 6, right: 6 },
    { row: '6', left: 6, right: 6 },
    { isAisle: true, label: 'ПРОХІД' },
    { row: '5Б', left: 6, right: 6 }, { row: '5А', left: 6, right: 6 },
    { row: '5', left: 6, right: 6 }, { row: '4', left: 6, right: 6 },
    { row: '3', left: 6, right: 6 }, { row: '2', left: 6, right: 6 },
    { row: '1', left: 6, right: 6 }
  ];

  // Генератор блоку місць (лівого або правого)
  const renderSeats = (rowCount, rowLabel, startSeatNum) => {
    return Array.from({ length: rowCount }).map((_, i) => {
      const seatNum = startSeatNum + i;
      const seatId = `${rowLabel}-${seatNum}`;
      const isOccupied = occupiedSeats.includes(seatId);
      const isSelected = selectedSeats.some(s => s.id === seatId);

      let className = 'seat available'; // За замовчуванням зелені
      if (isOccupied) className = 'seat occupied'; // Червоні
      else if (isSelected) className = 'seat selected'; // Сині (обрані)

      return (
        <button
          key={seatId}
          className={className}
          onClick={() => toggleSeat(rowLabel, seatNum)}
          disabled={isOccupied}
        >
          {isSelected || isOccupied ? seatNum : ''}
        </button>
      );
    });
  };

  return (
    <div className="hall-wrapper">
      <h2>Органний зал</h2>
      
      <div className="hall-container">
        {hallConfig.map((item, index) => {
          if (item.isAisle) {
            return <div key={`aisle-${index}`} className="aisle-marker">{item.label}</div>;
          }

          return (
            <div key={`row-${item.row}`} className="row-wrapper">
              <span className="row-label">{item.row}</span>
              
              <div className="seats-group">
                {renderSeats(item.left, item.row, 1)}
              </div>
              
              <div className="center-aisle"></div>
              
              <div className="seats-group">
                {/* Права сторона починає нумерацію після лівої */}
                {renderSeats(item.right, item.row, item.left + 1)}
              </div>
              
              <span className="row-label">{item.row}</span>
            </div>
          );
        })}
      </div>

      <div className="stage-container">
        <div className="stage">СЦЕНА</div>
        <p className="stage-subtitle">Тут творять магію музики</p>
      </div>

      {/* Легенда */}
      <div className="legend">
        <div className="legend-item"><span className="seat available legend-dot"></span> Вільне</div>
        <div className="legend-item"><span className="seat occupied legend-dot"></span> Зайняте</div>
        <div className="legend-item"><span className="seat selected legend-dot"></span> Обране</div>
      </div>
    </div>
  );
}

export default App;