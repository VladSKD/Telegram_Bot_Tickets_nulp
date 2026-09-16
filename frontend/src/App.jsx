import { useState, useEffect } from 'react';
import './App.css';

const tg = window.Telegram?.WebApp;

function App() {
  // Зчитуємо параметри з URL відразу
  const queryParams = new URLSearchParams(window.location.search);
  const initialOccupied = queryParams.get('occ') ? queryParams.get('occ').split(',') : [];
  const isAdmin = queryParams.get('admin') === 'true';
  const isSetupMode = queryParams.get('mode') === 'admin_setup';
  const eventId = queryParams.get('ev_id');

  const [selectedSeats, setSelectedSeats] = useState([]);
  const [occupiedSeats] = useState(initialOccupied);

  useEffect(() => {
    if (tg) {
      tg.expand();
      tg.ready();
      // Ховаємо системну кнопку Telegram, оскільки тепер у нас є своя на сайті
      tg.MainButton.hide(); 
    }
  }, []);

  const toggleSeat = (row, seatNum) => {
    const seatId = `${row}-${seatNum}`;
    const isOccupied = occupiedSeats.includes(seatId);

    if (isAdmin) {
      // Адмін дізнається інфо: можна клікати ТІЛЬКИ по зайнятих місцях
      if (!isOccupied) return;
      setSelectedSeats(prev => prev.some(s => s.id === seatId) ? [] : [{ id: seatId, row, seat: seatNum }]);
    } else {
      // Покупець АБО режим налаштування залу
      // Блокуємо клік, тільки якщо це не режим налаштування і місце вже зайняте
      if (!isSetupMode && isOccupied) return;
      
      setSelectedSeats(prev => {
        if (prev.some(s => s.id === seatId)) {
          return prev.filter(s => s.id !== seatId);
        }
        return [...prev, { id: seatId, row, seat: seatNum }];
      });
    }
  };

  const handleActionClick = () => {
    if (selectedSeats.length === 0) return;

    if (tg && tg.sendData) {
      if (isAdmin) {
        tg.sendData(`admin_seat|${eventId}|${selectedSeats[0].row}-${selectedSeats[0].seat}`);
      } else {
        // Працює і для покупця, і для збереження місць адміном
        const dataString = selectedSeats.map(s => `${s.row}-${s.seat}`).join('|');
        tg.sendData(dataString);
      }
    } else {
      // Тестовий режим для звичайного браузера
      alert("Дані, які б відправились боту:\n" + selectedSeats.map(s => `${s.row}-${s.seat}`).join('|'));
    }
  };

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

  const renderSeats = (rowCount, rowLabel, startSeatNum) => {
    return Array.from({ length: rowCount }).map((_, i) => {
      const seatNum = startSeatNum + i;
      const seatId = `${rowLabel}-${seatNum}`;
      const isOccupied = occupiedSeats.includes(seatId);
      const isSelected = selectedSeats.some(s => s.id === seatId);

      let className = 'seat available';
      if (isOccupied) className = 'seat occupied';
      if (isSelected) className += ' selected';

      return (
        <button
          key={seatId}
          className={className}
          onClick={() => toggleSeat(rowLabel, seatNum)}
          disabled={(!isAdmin && !isSetupMode) && isOccupied}
        >
          {seatNum}
        </button>
      );
    });
  };

  // Визначаємо текст кнопки залежно від режиму
  let buttonText = "";
  if (isSetupMode) buttonText = `✅ ЗБЕРЕГТИ МІСЦЯ (${selectedSeats.length} шт.)`;
  else if (isAdmin && selectedSeats.length > 0) buttonText = `ДІЗНАТИСЯ ІНФО (Ряд ${selectedSeats[0].row}, Місце ${selectedSeats[0].seat})`;
  else buttonText = `🎟 КУПИТИ (${selectedSeats.length} шт.)`;

  return (
    <div className={`hall-wrapper ${isAdmin ? 'admin-mode' : ''}`}>
      <h2>Органний зал {(isAdmin || isSetupMode) ? '(АДМІН)' : ''}</h2>
      
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

      <div className="legend">
        <div className="legend-item"><span className="seat available legend-dot"></span> Вільне</div>
        <div className="legend-item"><span className="seat occupied legend-dot"></span> Зайняте</div>
        <div className="legend-item"><span className="seat selected legend-dot"></span> Обране</div>
      </div>

      {/* НОВА ФІЗИЧНА КНОПКА, ЯКА ЗАВЖДИ ПРАЦЮЄ */}
      {selectedSeats.length > 0 && (
        <div style={{ position: 'sticky', bottom: '20px', marginTop: '25px', display: 'flex', justifyContent: 'center', zIndex: 1000 }}>
          <button 
            onClick={handleActionClick}
            style={{
              backgroundColor: '#3182ce', color: 'white', border: 'none', 
              borderRadius: '12px', padding: '16px 30px', fontSize: '16px', 
              fontWeight: 'bold', boxShadow: '0 4px 15px rgba(49, 130, 206, 0.4)',
              cursor: 'pointer', width: '95%', maxWidth: '400px'
            }}
          >
            {buttonText}
          </button>
        </div>
      )}
    </div>
  );
}

export default App;
