import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class MaterialStatusListener(Node):

    def __init__(self):
        super().__init__('material_status_listener')

        self.subscription = self.create_subscription(
            String,
            '/material_status',
            self.listener_callback,
            10
        )

        self.get_logger().info("Material status listener started.")

    def listener_callback(self, msg):

        if msg.data == "material_reached":
            self.get_logger().info("Material reached detected.")
            
            # Trigger UR5e routine here

            self.start_pick_and_place()

    def start_pick_and_place(self):

        self.get_logger().info("Starting UR5e pick-and-place process...")


def main(args=None):

    rclpy.init(args=args)

    node = MaterialStatusListener()

    rclpy.spin(node)

    node.destroy_node()

    rclpy.shutdown()


if __name__ == '__main__':
    main()