import { useState, useEffect } from 'react';
import './App.css';

const tg = window.Telegram.WebApp;

function App() {
  const [selectedSeats, setSelectedSeats] = useState([]);

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

    setSelectedSeats(prev => {
      if (prev.some(s => s.id === seatId)) {
        return prev.filter(s => s.id !== seatId);
      }
      return [...prev, { id: seatId, row, seat: seatNum }];
    });
  };

  // Конфігурація залу (зверху вниз, 14-24)
  const hallConfigTop = [
    { row: '24', left: 3, right: 3 }, { row: '23', left: 3, right: 3 },
    { row: '22', left: 3, right: 3 }, { row: '21', left: 3, right: 3 },
    { row: '20', left: 3, right: 3 }, { row: '19', left: 3, right: 3 },
    { row: '18', left: 3, right: 3 }, { row: '17', left: 3, right: 3 },
    { row: '16', left: 3, right: 3 }, { row: '15', left: 3, right: 3 },
    { row: '14', left: 3, right: 3 }
  ];

  // Конфігурація проходу та літерних рядів (12Б-6)
  const hallConfigMiddle = [
    { row: '13', left: 6, right: 6 },
    { isAisle: true, label: 'ПРОХІД' },
    { row: '12Б', left: 6, right: 6 }, { row: '12А', left: 6, right: 6 },
    { row: '12', left: 6, right: 6 }, { row: '11', left: 6, right: 6 },
    { row: '10', left: 6, right: 6 }, { row: '9', left: 6, right: 6 },
    { row: '8', left: 6, right: 6 }, { row: '7', left: 6, right: 6 },
    { row: '6', left: 6, right: 6 },
  ];

  // Конфігурація нижніх рядів (1-5Б)
  const hallConfigBottom = [
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
      const isSelected = selectedSeats.some(s => s.id === seatId);

      let className = 'seat available'; // За замовчуванням всі місця вільні та зелені
      if (isSelected) className = 'seat selected'; // Сині (обрані)

      return (
        <button
          key={seatId}
          className={className}
          onClick={() => toggleSeat(rowLabel, seatNum)}
        >
          {seatNum}
        </button>
      );
    });
  };

  const renderRow = (item, index) => {
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
  };

  return (
    <div className="hall-floorplan">
      
      {/* 1. ВЕРХНЯ ЧАСТИНА (Окремі зони) */}
      <div className="top-area">
        <div className="floorplan-box toilet-box">Місце туалету</div>
        <div className="floorplan-box chamber-space-box">Камерний Мистецький Простір</div>
      </div>

      {/* 2. СЕРЕДНЯ ЧАСТИНА (Зал + Бічні зони) */}
      <div className="middle-section">
        
        {/* ЛІВА ЧАСТИНА */}
        <div className="left-area">
          <div className="floorplan-box gallery-box">Галерея</div>
          <div className="floorplan-box synergy-box">Синерсія</div>
        </div>

        {/* ЗАЛ З МІСЦЯМИ */}
        <div className="main-seating-area">
          <div className="hall-container">
            {hallConfigTop.map((item, index) => renderRow(item, `top-${index}`))}
            {hallConfigMiddle.map((item, index) => renderRow(item, `mid-${index}`))}
            {hallConfigBottom.map((item, index) => renderRow(item, `bot-${index}`))}
          </div>
        </div>

        {/* ПРАВА ЧАСТИНА */}
        <div className="right-area">
          <div className="floorplan-box reception-box">Рецепція</div>
        </div>
      </div>

      {/* 3. НИЖНЯ ЧАСТИНА (Сцена) */}
      <div className="stage-container">
        <div className="stage">СЦЕНА</div>
        <p className="stage-subtitle">Тут творять магію музики</p>
      </div>

      {/* Легенда (Оновлена, без "Зайняте") */}
      <div className="legend">
        <div className="legend-item"><span className="seat available legend-dot"></span> Вільне</div>
        <div className="legend-item"><span className="seat selected legend-dot"></span> Обране</div>
      </div>
    </div>
  );
}

export default App;