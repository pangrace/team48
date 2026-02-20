import { createContext, useContext, type ReactNode } from "react";
import { theme } from "../theme";

type ThemeType = typeof theme;

interface ThemeContextProps {
  theme: ThemeType;
}

const ThemeContext = createContext<ThemeContextProps | undefined>(undefined);

export const ThemeProvider = ({ children }: { children: ReactNode }) => {


  return (
    <ThemeContext.Provider value={{ theme }}>
      <div
        style={{
          backgroundColor: theme.colors.background,
          color: theme.colors.text,
          minHeight: "100vh"
        }}
      >
        {children}
      </div>
    </ThemeContext.Provider>
  );
};

export const useTheme = () => {
  const context = useContext(ThemeContext);
  if (!context) throw new Error("useTheme must be used inside ThemeProvider");
  return context;
};
