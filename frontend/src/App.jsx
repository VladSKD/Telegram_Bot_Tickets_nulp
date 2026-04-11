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

  const renderSeats = (rowCount, rowLabel, startSeatNum, alignRight = false) => {
    return (
      <div className={`seats-group ${alignRight ? 'align-right' : 'align-left'}`}>
        {Array.from({ length: rowCount }).map((_, i) => {
          const seatNum = startSeatNum + i;
          const seatId = `${rowLabel}-${seatNum}`;
          const isSelected = selectedSeats.some(s => s.id === seatId);

          return (
            <button
              key={seatId}
              className={`seat ${isSelected ? 'selected' : ''}`}
              onClick={() => toggleSeat(rowLabel, seatNum)}
            >
              {seatNum}
            </button>
          );
        })}
      </div>
    );
  };

  return (
    <div className="app-container">
      <div className="floorplan-wrapper">
        
        {/* ЛІВЕ КРИЛО (Кімнати та коридори) */}
        <div className="left-wing">
          <div className="room wc-room">
            <div className="wc-box">WC</div>
          </div>
          <div className="room chamber-room">
            <span className="room-text">Камерний<br/>мистецький<br/>простір</span>
          </div>
          <div className="room synergy-room">
            <span className="room-text">Синергія<br/>живопису<br/>і музики</span>
          </div>
          <div className="room gallery-room">
            <div className="pillar thin-pillar-left"></div>
            <span className="room-text">Галерея</span>
            <div className="pillar square-pillar"></div>
          </div>
          <div className="room reception-room">
            <div className="pillar tall-pillar"></div>
            <span className="room-text">Рецепція</span>
            <div className="pillar huge-pillar"></div>
          </div>
        </div>

        {/* ЦЕНТРАЛЬНИЙ ЗАЛ (Місця) */}
        <div className="main-hall">
          
          {/* ВЕРХНІЙ БЛОК (Ряди 24-14) */}
          <div className="seating-block top-block">
            {['24', '23', '22', '21', '20', '19', '18', '17', '16', '15', '14'].map(row => (
              <div key={row} className="row-wrapper">
                <span className="row-label">{row}</span>
                {renderSeats(3, row, 1, true)} {/* alignRight = true */}
                <div className="center-aisle"></div>
                {renderSeats(3, row, 4, false)}
                <span className="row-label">{row}</span>
              </div>
            ))}
          </div>

          <div className="row-wrapper row-13">
             <span className="row-label">13</span>
             {renderSeats(6, '13', 1)}
             <div className="center-aisle"></div>
             {renderSeats(6, '13', 7)}
             <span className="row-label">13</span>
          </div>

          <div className="aisle-marker">ПРОХІД</div>

          {/* СЕРЕДНІЙ БЛОК (Ряди 12Б-6) */}
          <div className="seating-block middle-block">
            {['12Б', '12А', '12', '11', '10', '9', '8', '7', '6'].map(row => (
              <div key={row} className="row-wrapper">
                <span className="row-label">{row}</span>
                {renderSeats(6, row, 1)}
                <div className="center-aisle wide-aisle"></div>
                {renderSeats(6, row, 7)}
                <span className="row-label">{row}</span>
              </div>
            ))}
          </div>

          <div className="aisle-marker">ПРОХІД</div>

          {/* НИЖНІЙ БЛОК (Ряди 5Б-1) */}
          <div className="seating-block bottom-block">
            {['5Б', '5А', '5', '4', '3', '2', '1'].map(row => (
              <div key={row} className="row-wrapper">
                <span className="row-label">{row}</span>
                {renderSeats(6, row, 1)}
                <div className="center-aisle wide-aisle"></div>
                {renderSeats(6, row, 7)}
                <span className="row-label">{row}</span>
              </div>
            ))}
          </div>

          {/* СЦЕНА */}
          <div className="stage-area">
            <div className="stage-arc"></div>
            <div className="stage-title">СЦЕНА</div>
            <div className="stage-subtitle">Тут творять магію музики</div>
          </div>
        </div>

        {/* ПРАВЕ КРИЛО (Стовпи) */}
        <div className="right-wing">
           <div className="pillar square-pillar-right"></div>
           <div className="pillar huge-pillar-right"></div>
        </div>

      </div>
    </div>
  );
}

export default App;