static ft_force stat_force;
static ft_torque stat_torque;

void convert_ft(const ros_ft_pub::forcetorque::ConstPtr& src,
		ft_force **force, ft_torque **torque)
{
	if (!*force)
		*force = &stat_force;
	(*force)->x = src->force.x;
	(*force)->y = src->force.y;
	(*force)->z = src->force.z;

	if (!*torque)
		*torque = &stat_torque;
	(*torque)->x = src->torque.x;
	(*torque)->y = src->torque.y;
	(*torque)->z = src->torque.z;
}

void convert_ft_free(ft_force **force, ft_torque **torque)
{
	// Nothing here.
}
