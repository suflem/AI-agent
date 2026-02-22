type RobotMarkProps = {
  compact?: boolean;
};

export function RobotMark({ compact = false }: RobotMarkProps) {
  return (
    <div className={compact ? "robot-mark robot-mark-compact" : "robot-mark"}>
      <span className="robot-eye" />
      <span className="robot-eye" />
      {!compact ? <span className="robot-mouth" /> : null}
    </div>
  );
}
