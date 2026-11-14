import "./globals.css";

export const metadata = {
  title: "Ember | Environmental Fire Safety Dashboard",
  description:
    "Explore environmental and fuel parameters in an interactive fire safety dashboard preview.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
