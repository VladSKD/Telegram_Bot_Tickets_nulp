import { useState, useEffect } from 'react';
import './App.css'; 

const tg = window.Telegram.WebApp;

function App() {

  const [selectedSeats, setSelectedSeats] = useState([]);

  const rows = 10;
  const seatsPerRow = 15;

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

    return () => {
      tg.MainButton.offClick(handleMainButtonClick);
    };
  }, [selectedSeats]); 


  const toggleSeat = (row, seat) => {
    const seatId = `${row}-${seat}`; 
    
    setSelectedSeats(prev => {
      if (prev.some(s => s.id === seatId)) {
        return prev.filter(s => s.id !== seatId);
      }
      return [...prev, { id: seatId, row, seat }];
    });
  };

  return (
    <div className="hall-container">
      <h2>Органний Зал: Вибір Місця</h2>
      
      {/* Сцена */}
      <div className="stage">СЦЕНА</div>
      
      {/* Сітка Місць */}
      <div className="seats-grid">
        {Array.from({ length: rows }).map((_, rowIndex) => (
          <div key={`row-${rowIndex + 1}`} className="row-wrapper">
            <span className="row-label">Ряд {rowIndex + 1}</span>
            <div className="row-seats">
              {Array.from({ length: seatsPerRow }).map((_, seatIndex) => {
                const rowNum = rowIndex + 1;
                const seatNum = seatIndex + 1;
                const isSelected = selectedSeats.some(s => s.id === `${rowNum}-${seatNum}`);

                return (
                  <button
                    key={`${rowNum}-${seatNum}`}
                    className={`seat ${isSelected ? 'selected' : ''}`}
                    onClick={() => toggleSeat(rowNum, seatNum)}
                  >
                    {seatNum}
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default App;