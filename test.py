class A:

    def __init__(self, b):
        self.b = b

    def print(self):
        print(self.b)

def main():
    b = {"is_working": False}
    a = A(b)
    a.print()
    b["is_working"] = True
    a.print()

if __name__ == "__main__":
    main()