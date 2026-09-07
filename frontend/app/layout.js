import "./globals.css";

export const metadata = {
  title: "Inventory & Procurement Assistant",
  description: "Ask questions about stock and purchase orders in plain English",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
