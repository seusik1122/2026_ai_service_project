interface BadgeProps {
  label: string;
  color?: "blue" | "green" | "red" | "gray";
}

export default function Badge({ label, color = "blue" }: BadgeProps) {
  const colorMap = {
    blue: "bg-blue-100 text-blue-800",
    green: "bg-green-100 text-green-800",
    red: "bg-red-100 text-red-800",
    gray: "bg-gray-100 text-gray-800",
  };
  return (
    <span className={`px-2 py-1 rounded text-xs font-medium ${colorMap[color]}`}>
      {label}
    </span>
  );
}
