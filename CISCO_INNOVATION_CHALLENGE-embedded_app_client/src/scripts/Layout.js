import React from 'react';

function Layout({ children }) {
    return (
        <div>
            <div style={{
                backgroundColor: '#2C974B',
                color: 'white',
                padding: '1rem',
                fontSize: '1.2rem',
                fontWeight: 'bold'
            }}>
                Meraki Admin Dashboard
            </div>
            <div style={{ display: 'flex' }}>
                <div style={{ flexGrow: 1, padding: '2rem' }}>
                    {children}
                </div>
            </div>
        </div>
    );
}

export default Layout;
